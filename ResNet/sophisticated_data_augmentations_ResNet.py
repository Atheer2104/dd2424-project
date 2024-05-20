import torch
from torch import nn
from torchvision.transforms import v2

from torchsummary import summary

import model

from cutmix.utils import CutMixCrossEntropyLoss

import sys

sys.path.append("../")
from helpers import utils
from helpers import load_data_util as ldu


def he_initalization(m):
    for i in m.modules():
        if isinstance(i, torch.nn.Conv2d):
            torch.nn.init.kaiming_normal_(i.weight, mode="fan_in", nonlinearity="relu")


# this is the same as the ResNet paper
train_batch_size = 128

# setting batch size at test time to be 100 have division since we have 10k images at test time
test_batch_size = 100

test_transformations = v2.Compose(
    [
        v2.ToImage(),
        # change type of number and re-scale to [0.0, 1.0]
        v2.ToDtype(torch.float32, scale=True),
        # ! have to perform per-pixel mean subtraction
        v2.Normalize([0.4914, 0.4822, 0.4465], [0.2023, 0.1994, 0.2010]),
    ]
)

train_transformations = v2.Compose(
    [
        v2.ToImage(),
        # add 4 pixel zero padding
        v2.Pad(4),
        # 50% of horizontal flip
        v2.RandomHorizontalFlip(),
        # perform random crop back to size 32x32
        v2.RandomCrop(size=32),
        # change type of number and re-scale to [0.0, 1.0]
        v2.ToDtype(torch.float32, scale=True),
        # ! have to perform per-pixel mean subtraction
        v2.Normalize([0.4914, 0.4822, 0.4465], [0.2023, 0.1994, 0.2010]),
        # random erasing default parameters are close to what the original paper used for cifar 10, so no need to change
        v2.RandomErasing(),
    ]
)


def train(
    epochs,
    training_dataloader,
    ummodified_validation_dataloader,
    unmodified_training_dataloader,
    model,
    loss_fn,
    optimizer,
    lr_scheduler,
):

    loss = []

    # set the model on training model
    for current_epoch in range(0, epochs):
        print(f"current epoch: {current_epoch}")
        # print('current lr {:.5e}'.format(optimizer.param_groups[0]['lr']))
        running_loss = 0

        for batch_index, (X, y) in enumerate(training_dataloader):
            model.train()

            X, y = X.to(device), y.to(device)
            # print(f"{X.shape = }, {y.shape = }")

            # compute prediction error
            # here we are making the prediction
            trainig_pred = model(X)
            # computing the loss from our prediction and true val
            training_loss = loss_fn(trainig_pred, y)
            # print(f"(inside train) training_loss: {training_loss}")

            # there is something wrong with pytorch where the loss have to be used in someway to make it actually work cutmix or mixup
            running_loss += training_loss.item()

            # have to zero out the gradients, for each batch since they can be accumulated
            optimizer.zero_grad()

            # backpropagation
            training_loss.backward()

            # Adjust learning weights
            optimizer.step()

        loss.append(running_loss / len(training_dataloader))

        utils.compute_train_validation_loss_accuracy(
            current_epoch,
            model,
            loss_fn,
            device,
            unmodified_training_dataloader,
            ummodified_validation_dataloader,
        )
        # we step the lr scheduler this happens after each epoch
        lr_scheduler.step()

    print("training finished")


if __name__ == "__main__":
    device = (
        "cuda"
        if torch.cuda.is_available()
        else "mps" if torch.backends.mps.is_available() else "cpu"
    )
    print(f"Using {device} device")

    validation_set_size = 5000

    # if true use cifar 10 dataset otherwise cifar 100 data set is used
    use_Cifar10 = True
    use_her_parameters = False
    num_epochs_to_train = 400

    # cifar 10 dataset
    if use_Cifar10 is True:
        print("Dataset is CIFAR10")
        (
            unmodified_validation_loader,
            training_dataloader,
            unmodified_training_dataloader,
        ) = ldu.load_CIFAR10_train_validation(
            train_batch_size,
            train_transformations,
            validation_set_size,
            use_collate_fn=True,
        )
        test_dataloader = ldu.load_CIFAR10_test(test_batch_size, test_transformations)
        num_classes = 10

    else:
        print("Dataset is CIFAR100")
        (
            unmodified_validation_loader,
            training_dataloader,
            unmodified_training_dataloader,
        ) = ldu.load_CIFAR100_train_validation(
            train_batch_size,
            train_transformations,
            validation_set_size,
            use_collate_fn=True,
        )
        test_dataloader = ldu.load_CIFAR100_test(test_batch_size, test_transformations)
        num_classes = 100

    # for images, labels in unmodified_training_dataloader:
    #     print(
    #         f"(unmodified training) After CutMix/MixUp: {images.shape = }, {labels.shape = }"
    #     )
    #     break

    # for images, labels in training_dataloader:
    #     print(
    #         f"(modified training) After CutMix/MixUp: {images.shape = }, {labels.shape = }"
    #     )
    #     break

    resnet20 = model.resnet20(num_classes).to(device)
    resnet20.apply(he_initalization)

    resnet56 = model.resnet56(num_classes).to(device)
    resnet56.apply(he_initalization)

    resnet110 = model.resnet110(num_classes).to(device)
    resnet110.apply(he_initalization)

    # ! torch summary only works with cpu or cuda and not mps
    # print(summary(resnet20.to("cpu"), input_size=(3, 32, 32)))
    # print(summary(resnet56.to("cpu"), input_size=(3, 32, 32)))
    # print(summary(resnet110.to("cpu"), input_size=(3, 32, 32)))

    # for name, param in resnet20.named_parameters():
    #     if param.requires_grad:
    #         print(name, param.device)

    # defining loss function
    if use_her_parameters is True:
        print("using cross entropy loss with label smoothing")
        loss_fn = nn.CrossEntropyLoss(label_smoothing=0.1)
    else:
        print("using normal cross entropy loss")
        loss_fn = nn.CrossEntropyLoss()

    print(
        "------------- working on Sophistacted Data Augmentations ResNet20 -----------------"
    )
    if use_her_parameters is False:
        print("optimizer is SGD")
        optimizer = torch.optim.SGD(
            resnet20.parameters(), lr=0.1, momentum=0.9, weight_decay=0.0001
        )
    else:
        print("optimizer is AdamW")
        optimizer = torch.optim.AdamW(
            resnet20.parameters(), lr=0.1, weight_decay=0.0001
        )

    lr_scheduler = torch.optim.lr_scheduler.MultiStepLR(
        optimizer, [100, 150], gamma=0.1
    )
    train(
        num_epochs_to_train,
        training_dataloader,
        unmodified_validation_loader,
        unmodified_training_dataloader,
        resnet20,
        loss_fn,
        optimizer,
        lr_scheduler,
    )
    utils.evaluate(resnet20, test_dataloader, loss_fn, device)
    utils.plot_training_validation_loss_and_accuracy()
    utils.clear_histogram()

    print(
        "------------- working on Sophistacted Data Augmentations ResNet56 -----------------"
    )
    if use_her_parameters is False:
        print("optimizer is SGD")
        optimizer = torch.optim.SGD(
            resnet56.parameters(), lr=0.1, momentum=0.9, weight_decay=0.0001
        )
    else:
        print("optimizer is AdamW")
        optimizer = torch.optim.AdamW(
            resnet56.parameters(), lr=0.1, weight_decay=0.0001
        )

    lr_scheduler = torch.optim.lr_scheduler.MultiStepLR(
        optimizer, [100, 150], gamma=0.1
    )
    train(
        num_epochs_to_train,
        training_dataloader,
		unmodified_validation_loader,
		unmodified_training_dataloader,
        resnet56,
        loss_fn,
        optimizer,
        lr_scheduler,
    )
    utils.evaluate(resnet56, test_dataloader, loss_fn, device)
    utils.plot_training_validation_loss_and_accuracy()
    utils.clear_histogram()

    print(
        "------------------- working on Sophistacted Data Augmentations ResNet110 -----------------------"
    )
    # here we start with lr - 0.01 but after the first epoch this will be 0.1 and still divide it by 10 at 32k and 48k iterations
    if use_her_parameters is False:
        print("optimizer is SGD")
        optimizer = torch.optim.SGD(
            resnet110.parameters(), lr=0.01, momentum=0.9, weight_decay=0.0001
        )
    else:
        print("optimizer is AdamW")
        optimizer = torch.optim.AdamW(
            resnet110.parameters(), lr=0.01, weight_decay=0.0001
        )

    # here wer are increasing the lr after the first epoch
    increase_lr_after_first_epoch_scheduler = torch.optim.lr_scheduler.MultiStepLR(
        optimizer, [1], gamma=10
    )
    normal_multi_step_lr_scheduler = torch.optim.lr_scheduler.MultiStepLR(
        optimizer, [100, 150], gamma=0.1
    )

    lr_scheduler = torch.optim.lr_scheduler.ChainedScheduler(
        [increase_lr_after_first_epoch_scheduler, normal_multi_step_lr_scheduler]
    )
    train(
        num_epochs_to_train,
        training_dataloader,
		unmodified_validation_loader,
		unmodified_training_dataloader,
        resnet110,
        loss_fn,
        optimizer,
        lr_scheduler,
    )
    utils.evaluate(resnet110, test_dataloader, loss_fn, device)
    utils.plot_training_validation_loss_and_accuracy()
    utils.clear_histogram()
