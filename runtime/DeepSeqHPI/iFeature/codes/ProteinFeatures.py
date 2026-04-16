import numpy as np


class Features:

    aaToOneHot = {'Q': '1000000000000000000000',
                  'S': '0100000000000000000000',
                  'R': '0010000000000000000000',
                  'F': '0001000000000000000000',
                  'P': '0000100000000000000000',
                  'K': '0000010000000000000000',
                  'I': '0000001000000000000000',
                  'N': '0000000100000000000000',
                  'H': '0000000010000000000000',
                  'C': '0000000001000000000000',
                  'W': '0000000000100000000000',
                  'M': '0000000000010000000000',
                  'Y': '0000000000001000000000',
                  'A': '0000000000000100000000',
                  'V': '0000000000000010000000',
                  'E': '0000000000000001000000',
                  'G': '0000000000000000100000',
                  'L': '0000000000000000010000',
                  'T': '0000000000000000001000',
                  'D': '0000000000000000000100',
                  'U': '0000000000000000000010',
                  'X': '0000000000000000000001'
                  }

    maxSizeOneHot = 600



    def extractOneHot(protein):
        naminoacid = len(protein)
        features = np.empty([0, 0])

        for index in range(0, Features.maxSizeOneHot):
            if index < naminoacid:
                features = np.append(features, list(Features.aaToOneHot[protein[index]]))
            else:
                features = np.append(features, list('0000000000000000000000'))

        features = features.reshape(Features.maxSizeOneHot, 22)

        return features

