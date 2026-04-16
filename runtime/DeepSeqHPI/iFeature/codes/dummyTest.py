import readFasta
import pandas as pa
import numpy as np
import torch
import iFeature.codes.AAC as aac
import iFeature.codes.Geary as ac
import iFeature.codes.CTriad as ctriad
from ProteinFeatures import Features
import torch.utils.data as utils
import sys
import itertools

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
torch.set_num_threads(8)

hostFasta = readFasta.readFasta(sys.argv[1])
pathogenFasta = readFasta.readFasta(sys.argv[2])

feature = sys.argv[3]
modelType = sys.argv[4]
outputFileName = sys.argv[5]
pairwiseFilename = "noFile"
pairwiseDF = "noFile"
pairwiseListBool = 0

if len(sys.argv) > 6:
    pairwiseFilename = sys.argv[6]
    if pairwiseFilename != "nothing":
        pairwiseListBool = 1
        pairwiseDF = pa.read_csv(pairwiseFilename, sep='\t', header=None)
        pairsToTest = (pairwiseDF.iloc[:, 0] + pairwiseDF.iloc[:, 1]).values

vectorSize = 20

batch_size = 100

colNames = ['proteinA', 'seqA', 'proteinB', 'seqB']

testingDF = pa.DataFrame(columns=colNames)


for hostSequence in hostFasta:
     for pathogenSequence in pathogenFasta:
         if pairwiseListBool == 1:
            pair= hostSequence[0]+pathogenSequence[0]
            if pair in pairsToTest:
                testingDF.loc[len(testingDF)] = [hostSequence[0], hostSequence[1], pathogenSequence[0],pathogenSequence[1]]
         else:
             testingDF.loc[len(testingDF)] = [hostSequence[0], hostSequence[1], pathogenSequence[0],pathogenSequence[1]]



print(testingDF)