import torch
import torch.nn as nn
import time
import torch.utils.data as utils
import numpy as np
import pandas as pa
from ProteinFeatures import Features
from ConvolutionalNN import convNet



device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Hyper parameters
num_epochs = 5
num_classes = 10
batch_size = 10
learning_rate = 0.001

test = pa.read_csv("/home/cdloaiza/DeepSeqHPI/test.txt")

features = np.empty([Features.maxSizeOneHot, 44, 0])


for index, row in test.iterrows():
    feature = np.column_stack((Features.extractOneHot(row['seqA']), Features.extractOneHot(row['seqB'])))
    features = np.dstack((features, feature))

labels = np.append(np.ones([10]), np.zeros([10]))

features = features.astype(np.float32)
labels = labels.astype(np.float32)

tensor_x = torch.from_numpy(features) # transform to torch tensors
tensor_x = tensor_x.transpose(0, 2)
tensor_x = tensor_x.unsqueeze(1)
tensor_y = torch.from_numpy(labels)

testDataset = utils.TensorDataset(tensor_x, tensor_y)

# Data loader
test_loader = torch.utils.data.DataLoader(dataset=testDataset,
                                           batch_size=batch_size,
                                           shuffle=True)

model = torch.load("onehot_dummyModel.pth")
model.eval()

with torch.no_grad():
    correct = 0
    total = 0
    for ppp, labels in test_loader:
        ppp = ppp.to(device)
        labels = labels.to(device)
        outputs = model(ppp)
        _, predicted = torch.max(outputs.data, 1)
        total += labels.size(0)
        print(predicted)
        print(labels)
        correct += (predicted.float() == labels).sum().item()

    print('Test Accuracy of the model on the 10 test ppis: {} %'.format(100 * correct / total))
