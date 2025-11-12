# stats-car

a fun project to plot statistical data about car collections (such as in housing societies).

collect your own data, and use the this tool to plot the results.

example output:

<img width="1400" height="1000" alt="combined_distributions" src="https://github.com/user-attachments/assets/2092e616-f545-4ad6-9929-e83bf6ce39be" />



### preparation

- collect the car data in the format shown in the csv file in the `sample` folder. save it in a `cardata.csv` file.
- update the `car_classes.csv` file (if any data is missing/needs correction).

### how to use

if you have the default files ready as shown in the help, just run the below command, and the output files will be saved in the `car_stats_plots` folder.
```
% python car_stats.py
```

#### help

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

Do send a pull request or raise an issue if you find something wrong with the `car_classes.csv` file, or want to fix/improvem anything else too.
