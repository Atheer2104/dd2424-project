from VGG1 import VGG1
from VGG2 import VGG2
from VGG3 import VGG3

import sys

sys.path.append("../")

from baseline_combined_reguralizations.VGG3_BN_dropout import VGG3_BN_Dropput

import torch
from torch import nn
from torchvision import datasets
from torchvision.transforms import v2
from torch.utils.data import DataLoader

import matplotlib.pyplot as plt

from torchsummary import summary

train_model_training_loss_ls = []
train_model_training_accuracy_ls = []
validation_model_training_loss_ls = []
validation_model_training_accuracy_ls = []


def plot_training_validation_loss_and_accuracy():
    epochs = range(1, len(train_model_training_loss_ls) + 1)

    plt.figure(figsize=(12, 6))

    plt.subplot(1, 2, 1)
    plt.plot(epochs, train_model_training_loss_ls, "c", label="Training Loss")
    plt.plot(epochs, validation_model_training_loss_ls, "r", label="Validation Loss")
    plt.title("Training and Validation Loss")
    plt.xlabel("Epochs")
    plt.ylabel("Loss")
    plt.legend()

    plt.subplot(1, 2, 2)
    plt.plot(epochs, train_model_training_accuracy_ls, "c", label="Training Acc.")
    plt.plot(
        epochs, validation_model_training_accuracy_ls, "r", label="Validation Acc."
    )
    plt.title("Training and Validation Accuracy")
    plt.xlabel("Epochs")
    plt.ylabel("Accuracy")
    plt.legend()

    # plt.show()
    fname = f"figs/{time.strftime('%Y%m%d-%H%M%S')}"
    plt.savefig(fname)
    plt.close()


# load train and test dataset
def load_dataset():

    # defining the transfmorations that will be done on the image
    train_transforms = v2.Compose(
        [
            # convert the input from PIL image to Image which is analogy to a torch tensor
            v2.ToImage(),
            # performs random horizontal fliping where the default probability for flip is 0.5
            v2.RandomHorizontalFlip(),
            # here we are applying the height and width shift, we use the affine function where we can apply multiple
            # transformations at once, one which you have to apply is degrees which is to rotation the image by in our case
            # we don't want any transformations
            v2.RandomAffine(degrees=0, translate=(0.1, 0.1)),
            # changes the type of tensor to float32 and performs scaling so the value will be between [0,1] this happens
            # because the target type is float32
            v2.ToDtype(torch.float32, scale=True),
        ]
    )

    test_transforms = v2.Compose(
        [
            # convert the input from PIL image to Image which is analogy to a torch tensor
            v2.ToImage(),
            # changes the type of tensor to float32 and performs scaling so the value will be between [0,1] this happens
            # because the target type is float32
            v2.ToDtype(torch.float32, scale=True),
        ]
    )

    # load dataset
    training_data = datasets.CIFAR10(
        "../root",
        train=True,
        download=True,
        transform=train_transforms,
    )
    test_data = datasets.CIFAR10(
        "../root",
        train=False,
        download=True,
        transform=test_transforms,
    )

    return training_data, test_data


def create_dataloaders(batch_size, training_data, test_data):
    train_dataloader = DataLoader(training_data, batch_size=batch_size, shuffle=True)
    test_dataloader = DataLoader(test_data, batch_size=batch_size, shuffle=True)

    return train_dataloader, test_dataloader


def he_initalization(m):
    for i in m.modules():
        if isinstance(i, nn.Conv2d) or isinstance(i, nn.Linear):
            nn.init.kaiming_normal_(i.weight, mode="fan_in", nonlinearity="relu")
            nn.init.zeros_(i.bias)


def evaluate(model, dataloader, loss_fn):
    model.eval()

    dataset_size = len(dataloader.dataset)
    num_batches = len(dataloader)

    total_loss, num_correct = 0, 0

    # Disable gradient computation and reduce memory consumption.
    with torch.no_grad():
        for X, y in dataloader:
            X, y = X.to(device), y.to(device)

            # making predictions
            pred = model(X)

            # getting total loss
            total_loss += loss_fn(pred, y).item()

            num_correct += (pred.argmax(1) == y).type(torch.float).sum().item()

    total_loss /= num_batches
    num_correct /= dataset_size
    print(
        f"Test Data: \n Accuracy: {(100*num_correct):>0.3f}%, Avg loss: {total_loss:>8f} \n"
    )


def compute_loss_on_whole_dataloader(model, dataloader):
    running_loss = 0.0

    for valX, valy in dataloader:
        valX, valy = valX.to(device), valy.to(device)

        # make predictions
        validation_pred = model(valX.to(device))
        # compute loss
        validation_loss = loss_fn(validation_pred, valy.to(device))
        # update running loss
        running_loss += validation_loss.item()
        
    return running_loss / len(dataloader)


def compute_accuracy_on_whole_dataloader(model, dataloader):
    dataset_size = len(dataloader.dataset)

    num_correct = 0
    with torch.no_grad():
        for X, y in dataloader:
            X, y = X.to(device), y.to(device)

            # making predictions
            pred = model(X)

    num_correct = 0
    with torch.no_grad():
        for X, y in dataloader:
            X, y = X.to(device), y.to(device)

            # making predictions
            pred = model(X)

            num_correct += (pred.argmax(1) == y).type(torch.float).sum().item()

    return num_correct / dataset_size


def train(
    epochs, training_dataloader, validation_dataloader, model, loss_fn, optimizer
):
    # set the model on training model
    for current_epoch in range(0, epochs):
        print(f"current epoch: {current_epoch}")

        for batch_index, (X, y) in enumerate(training_dataloader):
            model.train()

            X, y = X.to(device), y.to(device)

            # compute prediction error
            # here we are making the prediction
            trainig_pred = model(X)
            # computing the loss from our prediction and true val
            loss = loss_fn(trainig_pred, y)

            # have to zero out the gradients, for each batch since they can be accumulated
            optimizer.zero_grad()

            # backpropagation
            loss.backward()

            # Adjust learning weights
            optimizer.step()

        # getting valiation loss now
        model.eval()

        training_loss = compute_loss_on_whole_dataloader(model, training_dataloader)
        validation_loss = compute_loss_on_whole_dataloader(model, validation_dataloader)

        train_model_training_loss_ls.append(training_loss)
        validation_model_training_loss_ls.append(validation_loss)

        training_acc = compute_accuracy_on_whole_dataloader(model, training_dataloader)
        validation_acc = compute_accuracy_on_whole_dataloader(
            model, validation_dataloader
        )

        train_model_training_accuracy_ls.append(training_acc)
        validation_model_training_accuracy_ls.append(validation_acc)

        training_acc = compute_accuracy_on_whole_dataloader(model, training_dataloader)
        validation_acc = compute_accuracy_on_whole_dataloader(
            model, validation_dataloader
        )

        train_model_training_accuracy_ls.append(training_acc)
        validation_model_training_accuracy_ls.append(validation_acc)

        # Print information out
        print(f"Epoch: {current_epoch}, Loss: {training_loss:.4f}")

    print("training finished")


if __name__ == "__main__":
    device = (
        "cuda"
        if torch.cuda.is_available()
        else "mps" if torch.backends.mps.is_available() else "cpu"
    )
    print(f"Using {device} device")

    batch_size = 64

    trainig_data, test_data = load_dataset()
    train_dataloader, test_dataloader = create_dataloaders(
        batch_size, trainig_data, test_data
    )

    # ! CHOOSE MODEL HERE

    # VGG1 = VGG1().to(device)
    # VGG1.apply(he_initalization)

    # VGG2 = VGG2().to(device)
    # VGG2.apply(he_initalization)

    # VGG3 = VGG3().to(device)
    # VGG3.apply(he_initalization)

    VGG3_BN_Dropput = VGG3_BN_Dropput().to(device)
    VGG3_BN_Dropput.apply(he_initalization)

    # print(summary(VGG1.to("cpu"), input_size=(3, 32, 32)))
    # print(summary(VGG2.to("cpu"), input_size=(3, 32, 32)))
    # print(summary(VGG3.to("cpu"), input_size=(3, 32, 32)))
    # print(summary(VGG3_BN_Dropput.to("cpu"), input_size=(3, 32, 32)))


    # defining loss function and optimizer
    loss_fn = nn.CrossEntropyLoss()
    optimize = torch.optim.SGD(VGG3_BN_Dropput.parameters(), lr=0.001, momentum=0.9)

    train(100, train_dataloader, test_dataloader, VGG3_BN_Dropput, loss_fn, optimize)  # training
    evaluate(VGG3_BN_Dropput, test_dataloader, loss_fn)  # evaluating
    plot_training_validation_loss_and_accuracy()
