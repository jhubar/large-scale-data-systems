import numpy as np

from collections import defaultdict

class MainWindow():
    def wordCount(text):
        counts=defaultdict(int)
        for word in text.split():
            counts[word.lower()] +=1
        return counts

    def map(key,value):
        intermediate=[]
        for word in value.split():
            intermediate.append((word, 1))
        return intermediate

    def reduce(key, values):
        result = 0
        for c in values:
            result = result +c
        return (key, result)




    if __name__ == "__main__":
        lot1 = "jour lève notre grisaille"
        lot2 = "trottoir notre ruelle notre tour"
        lot3 = "jour lève notre envie vous"
        lot4 = "faire comprendre tous notre tour"
        lots = np.array([lot1,lot2,lot3,lot4]).tolist()
        maps = []
        v = defaultdict(list)
        for lot in lots:
            maps.append(map(1,lot))
        mapsFlattened = [ (key, values) for map in maps for (key, values) in map]

        print(sorted(mapsFlattened))

        for key, value in sorted(mapsFlattened):
            v[value].append(key)

        print(v)
