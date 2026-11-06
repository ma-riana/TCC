## WORKLOADS UTILIZADOS

### Dataset pequeno 

python csv_generator.py --volume small --secondary-sources 2 --secondary-volume 0.2 0.4 --output-dir csvs_small --seed 100

### Dataset médio 

python csv_generator.py --volume medium --secondary-sources 4 --secondary-volume 0.3 --output-dir csvs_medium --seed 200

### Dataset grande

python csv_generator.py --volume large --secondary-sources 5 --secondary-volume 0.1 0.15 0.2 --output-dir csvs_large --seed 300