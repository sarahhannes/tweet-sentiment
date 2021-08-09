import glob
import pandas as pd

# TODO: if /data/raw/*_raw.csv exist, open and append, rename file to {end_date}_raw.csv
filename = glob.glob('./data/raw/*_raw.csv')[0]
df = pd.read_csv(filename)


# TODO: Otherwise write and name file {end_date}_raw.csv
