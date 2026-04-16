import readFasta
import iFeature.codes.CTriad as ctriad
import iFeature.codes.Geary as ac
import pandas as pa
import numpy as np
import torch


fastas = readFasta.readFasta("test-protein.txt")
print([fastas[0]])
print(ac.Geary([fastas[0]]))
print(len(ac.Geary([fastas[0]])[1]))

features = np.empty([44, 0])
hpidb = pa.read_csv("hpidb2.seq.toy.txt")

record = np.append(ctriad.CTriad([hpidb[1:2].iloc[0]])[1][1:81], ctriad.CTriad([hpidb[3:4].iloc[0]])[1][1:81])

print(record)


