import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt

def time_convertor(input):

    splited = input.split(':')
    return float(splited[2])


if __name__ == '__main__':


    # Import the json in a dataframe
    data_file = open('crash_data.json')
    json_str = data_file.read()
    json_data = json.loads(json_str)
    json_data = json_data['data']

    # Convert the time:
    for item in json_data:
        item['time'] = time_convertor(item['time'])

    # Convert to dataframe:
    df = pd.DataFrame(json_data)

    #Make the mean:
    means = df.groupby('number node')['time'].mean()
    print(means)
    #means = np.sort(means)
    #means = means[::-1]
    idx = [10, 9, 8, 7, 6]

    means = [22.879449, 22.625959,22.794184,23.148774,23.256365]

    plt.scatter(df['number node'], df['time'])
    plt.plot(means)
    plt.title("Effect of the random faulty computers rate on the consensus time")
    plt.xlabel('Number of valid computer in the 10 computer cluster')
    plt.ylabel('Computing duration (seconds)')
    plt.savefig('random_expe.pdf')
    plt.show()

