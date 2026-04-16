import torch.nn as nn
import torch

class convNet(nn.Module):

    def __init__(self, num_classes=1):
        super(convNet, self).__init__()
        self.features = nn.Sequential(
            nn.Conv1d(1, 10, kernel_size=5, stride=1, padding=2),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=2, stride=2),
            nn.Conv1d(10, 50, kernel_size=5, stride=1, padding=3),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=2, stride=2),
        )

        self.classifier = nn.Sequential(
            nn.Linear(64*50, 480),
            nn.ReLU(inplace=True),
            nn.Dropout(),
            nn.Linear(480, 480),
            nn.ReLU(inplace=True),
            nn.Linear(480, num_classes),
	        nn.Sigmoid(),
        )

    def forward(self, x):
        ##print(x.size())
        x = self.features(x)
        ##print(x.size())
        x = x.view(x.size(0), 64*50)
        x = self.classifier(x)
        return x
