import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt

def time_convertor(input):

    splited = input.split(':')
    return float(splited[2])


if __name__ == '__main__':


    # Import the json in a dataframe
    data_file = open('data_experimental.json')
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
    idx = [4, 5, 6, 7]

    plt.scatter(df['number node'], df['time'])
    plt.plot(means)
    plt.show()

