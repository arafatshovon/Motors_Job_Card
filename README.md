# Motors-Job-Card

## Live Access

Link : [http://192.168.100.113:9001](http://192.168.100.113:9001)

```
username : misadmin
password : acimisai 
```

### How to Start and Stop the Project
First login into server and open a terminal, Then type the following command for starting or stoping the project

```
sudo systemctl start/stop/status/restart motors_job_card.service
```

### API
```
Swagger UI: http://192.168.100.113:9001/api/docs/

OpenAPI schema: http://192.168.100.113:9001/api/schema/

Checkout API: http://192.168.100.113:9001/api/checkout?chassis=RG642003173&mileage=4000

Search bike names (typeahead): http://192.168.100.113:9001/api/bikes/search?query=cb&limit=20&offset=0

Bike names from warranty claims only: http://192.168.100.113:9001/api/bikes/names

Top warranty parts: http://192.168.100.113:9001/api/warranty/top-parts?from_date=2025-01-01&to_date=2026-01-19&limit=30

Top warranty parts (to_date defaults to today): http://192.168.100.113:9001/api/warranty/top-parts?from_date=2025-01-01&limit=30

Top warranty parts by bike model: http://192.168.100.113:9001/api/warranty/top-parts/by-bike-model?from_date=2025-01-01&to_date=2026-01-19&limit=30

Top warranty parts for a specific bike model: http://192.168.100.113:9001/api/warranty/top-parts/for-bike-model?bike_model=Model%20Name&from_date=2025-01-01&to_date=2026-01-19&limit=5

Warranty failure ratio by bike model: http://192.168.100.113:9001/api/warranty/failure-ratio/by-bike-model?limit=100
```
