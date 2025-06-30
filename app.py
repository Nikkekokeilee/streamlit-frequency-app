import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import datetime

# Simulate frequency data similar to Excel example
timestamps = [datetime.datetime.now() - datetime.timedelta(seconds=30*i) for i in range(30)][::-1]
frequencies = [50 + np.random.uniform(-0.2, 0.2) for _ in range(30)]

# Create DataFrame
df = pd.DataFrame({'Timestamp': timestamps, 'FrequencyHz': frequencies})

# Assign colors based on frequency values
def get_color(freq):
    if freq < 50:
        return 'red'
    elif freq > 50:
        return 'blue'
    else:
        return 'white'

df['Color'] = df['FrequencyHz'].apply(get_color)

# Plot
plt.figure(figsize=(10, 5))
plt.scatter(df['Timestamp'], df['FrequencyHz'], c=df['Color'], s=60, edgecolors='black')
plt.plot(df['Timestamp'], df['FrequencyHz'], color='gray', linestyle='--', alpha=0.5)
plt.axhline(50, color='black', linewidth=0.8, linestyle=':')
plt.title('Frequency Over Time')
plt.xlabel('Timestamp')
plt.ylabel('Frequency (Hz)')
plt.ylim(49.5, 50.5)
plt.xticks(rotation=45)
plt.tight_layout()
plt.grid(True)
plt.show()

