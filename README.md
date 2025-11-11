# stats-car

### how to use

run help command

```
% python car_stats.py -h
usage: car_stats.py [-h] [--cardata CARDATA] [--classes CLASSES] [--outdir OUTDIR] [--show]

Compute statistics and combined plots for surveyed car data.

options:
  -h, --help         show this help message and exit
  --cardata CARDATA  CSV file with observed cars (default cardata.csv)
  --classes CLASSES  CSV file with maker/model -> class,fuel (default car_classes.csv)
  --outdir OUTDIR    Folder to save outputs (default ./car_stats_plots)
  --show             Show plots interactively
```

if you have the default inputs ready as shown in the help command, just run the below command, and the output data will be saved in the `car_stats_plots` folder.
```
% python car_stats.py
```
