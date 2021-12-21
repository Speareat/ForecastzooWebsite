# -*- coding: utf-8 -*-
"""
Created on Mon Nov 22 12:12:52 2021

@author: augus
"""

import pandas as pd
import numpy as np
import datetime
from matplotlib import pyplot as plt

def getHosp():
    import pandas as pd
    import datetime
    dataHospi = pd.read_csv('COVID19BE_HOSP.csv')
    dataHospi = dataHospi[['DATE','PROVINCE','REGION','NEW_IN']]
    hospitals_entries_mean = pd.DataFrame(columns=['DATE','PROVINCE','REGION','NEW_IN'])
    provinces = list(set(dataHospi['PROVINCE'].tolist()))
    
    
    L = 7 # number of days to take into account when computing the average for hospitalizations
    for province in provinces:
        prov_data = dataHospi.loc[dataHospi['PROVINCE'] == province][['DATE', 'REGION', 'NEW_IN']]
        act_tab = []
        act_sum = 0
        i = 0
        center = int(L/2)
        for _ in range(L):
            act_tab.append(prov_data.iloc[i]['NEW_IN'])
            act_sum += act_tab[i]
            i += 1
        while i < len(prov_data):
            row_center = prov_data.iloc[center]
            values = {'DATE':row_center['DATE'], 'PROVINCE':province, 'REGION':row_center['REGION'], 'NEW_IN':act_sum/L}
            hospitals_entries_mean = hospitals_entries_mean.append(values, ignore_index=True)
            act_sum -= act_tab[0]
            act_tab.remove(act_tab[0])
            i += 1
            center += 1
            if i < len(prov_data):
                act_tab.append(prov_data.iloc[i]['NEW_IN'])
                act_sum += act_tab[L-1]
                
    hosp_prov = hospitals_entries_mean.loc[hospitals_entries_mean['PROVINCE'] == province][['DATE', 'NEW_IN']]
    
    
    start_time = datetime.datetime.strptime(hosp_prov.iloc[-1]['DATE'], '%Y-%m-%d')
    
    dates = [(start_time+datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1, 31)]
    df2 = pd.DataFrame({'DATE': dates, 'NEW_IN': [None for i in range(1, 31)]})
    hosp_prov = hosp_prov.append(df2)
    return hosp_prov

hp = getHosp()
x = hp['DATE'].tolist()
for i in range(len(x)):
    tab = x[i].split('-')
    x[i] = tab[2]+'-'+tab[1]
y = hp['NEW_IN'].tolist()
plt.plot(x, y)
plt.xticks(ticks=[x[i] for i in range(0,len(x), 3)])
plt.savefig("background.png")
plt.ylim((0, 3*np.max(y[:9])))
plt.show()
print(3*np.max(y[:9]))
# getHosp().plot(x='DATE', y = 'NEW_IN', grid=True)