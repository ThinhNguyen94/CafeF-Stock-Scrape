# -*- coding: utf-8 -*-
"""
Created on Tue Oct 27 20:07:20 2020

@author: LENOVO
"""
import pandas as pd
import os
import mysql.connector

vnstock_conn = mysql.connector.connect(
    host = 'localhost',
    username = 'root',
    password = 'GuardianSQL1994',
    database = 'vn_stock'
    )    # this will create a database connection object
print('MySQL connection is created !') 

### Import stock data from csv
## List all files in targeted directory
path = "D:/Data/VN-Stocks"  # define the path (i.e. folder dir contains all data csv files)
files = []   # empty list to store file dirs
for r, d, f in os.walk(path):
    for file in f:
        if '.csv' in file:
            files.append(os.path.join(r, file))

for f in files:
    print(f)
    
