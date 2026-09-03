FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
# Install the lightweight core needed to run the pipeline end-to-end;
# swap in the full requirements.txt for the dbt/Airflow production path.
RUN pip install --no-cache-dir pandas numpy scikit-learn matplotlib

COPY . .

CMD ["sh", "-c", "python src/extract.py && python src/load.py --engine sqlite && python src/transform_local.py && python ml/sales_forecast.py && python src/export_for_powerbi.py"]
