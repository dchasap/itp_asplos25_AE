
import pandas as pd
import matplotlib.pyplot as plt

# Load the CSV file into a DataFrame
df = pd.read_csv('data/access_freq_filter_analysis/TEST/srv105_ap_TEST_address_access_stats_cpu0_L2C.csv')

# Plot a histogram of accesses
plt.figure()
field = 'misses'
scale = 'linear'
#plt.hist(df['accesses'], bins=50, alpha=0.5)
plt.hist(df[field], bins=50, alpha=0.8)
plt.xlabel(field)
plt.ylabel('Frequency')
plt.title('Histogram of Accesses')
plt.yscale(scale)
#plt.show()

plt.savefig('figures/access_freq_hist_' + field + '_' + scale + '_srv105.pdf')
# Plot a histogram of addresses
#plt.figure()
#plt.hist(df['address'], bins=50)
#plt.xlabel('Address')
#plt.ylabel('Frequency')
#plt.title('Histogram of Addresses')
#plt.show()