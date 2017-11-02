# Rigol1000z
Python USB library to control Rigol DS1000z oscilloscopes.

```python
import rigol1000z

osc = rigol1000z.Rigol1000z()

# Change voltage range of channel 1 to 50mV/div.
osc[1].set_vertical_scale_V_div(50e-3)

# Stop the scope.
osc.stop()

# Take a screenshot.
osc.get_screenshot('screenshot.png', 'png')

# Capture the data sets from channels 1--4 and
# write the data sets to their own file.
for c in range(1,5):
    osc[c].get_data('raw', 'channel%i.dat' % c)
```
