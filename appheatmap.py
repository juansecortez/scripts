import rasterio
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import create_engine
import utm

# Configuración de la conexión a la base de datos
server = '192.168.200.31'
database = 'jmineops'
username = 'tinformacion'
password = 'Timeinlondon$'
conn_str = f"mssql+pyodbc://{username}:{password}@{server}/{database}?driver=ODBC+Driver+17+for+SQL+Server"
engine = create_engine(conn_str)

# Consulta SQL para obtener los datos
print("Iniciando la consulta SQL...")
query = """
SELECT TOP 500 [time]
      ,[Northing] AS j
      ,[Easting] AS i
      ,[Elevation]
      ,[speed] AS Speed
      ,[full_name]
      ,[Alarma]
  FROM [jmineops].[dbo].[T_sensors_speed_coord]
"""

data = pd.read_sql(query, engine)
print(f"Consulta SQL completada. Se obtuvieron {len(data)} registros.")

# Convertir las coordenadas UTM a latitud y longitud
def utm_to_latlon(row):
    lat, lon = utm.to_latlon(row['i'], row['j'], 13, 'N')  # Ajustar la zona y el hemisferio según sea necesario
    return pd.Series([lat, lon])

data[['latitude', 'longitude']] = data.apply(utm_to_latlon, axis=1)

# Filtrar datos para eliminar coordenadas inválidas
valid_lat_range = (18, 22)
valid_lon_range = (-107, -100)
data = data[(data['latitude'].between(*valid_lat_range)) & (data['longitude'].between(*valid_lon_range))]

# Convertir la columna 'time' a datetime
data['time'] = pd.to_datetime(data['time'])

# Eliminar filas con valores faltantes y velocidades mayores a 50 km/h
data = data.dropna(subset=['latitude', 'longitude', 'Speed', 'Alarma', 'Elevation'])
data = data[data['Speed'] <= 50]
print("Datos filtrados y preparados.")

# Ruta al archivo GeoTIFF
geotiff_path = 'Pea-Colorada-PeCo_Orto_Feb2024-57-dsm.tif'  # Cambia esta ruta al archivo GeoTIFF

# Leer y procesar el archivo GeoTIFF
print("Leyendo el archivo GeoTIFF...")
with rasterio.open(geotiff_path) as src:
    # Usar un submuestreo para reducir el tamaño de los datos cargados
    scale_factor = 20
    height, width = src.shape
    transform = src.transform

    # Leer una ventana con submuestreo
    elevation_data = src.read(
        1,
        out_shape=(height // scale_factor, width // scale_factor),
        resampling=rasterio.enums.Resampling.average
    )
    
    # Calcular las coordenadas de la malla
    x_coords = np.linspace(transform.c, transform.c + transform.a * (width // scale_factor), width // scale_factor)
    y_coords = np.linspace(transform.f, transform.f + transform.e * (height // scale_factor), height // scale_factor)
    x, y = np.meshgrid(x_coords, y_coords)

print("Lectura del GeoTIFF completada.")

# Verificar rango de elevación para asegurar la visibilidad
z_min, z_max = np.min(elevation_data), np.max(elevation_data)
print(f"Rango de elevación: {z_min} a {z_max}")

# Crear la figura 3D con Plotly
print("Creando visualización 3D con Plotly...")
fig = go.Figure()

# Añadir la superficie de elevación
fig.add_trace(go.Surface(
    z=elevation_data, 
    x=x, 
    y=y, 
    colorscale='Viridis', 
    cmin=z_min, 
    cmax=z_max,
    opacity=0.8,
    showscale=False
))

# Añadir los puntos de velocidad como un scatter 3D
fig.add_trace(go.Scatter3d(
    x=data['longitude'],
    y=data['latitude'],
    z=data['Elevation'],
    mode='markers',
    marker=dict(
        size=5,
        color=data['Speed'],  # Color según la velocidad
        colorscale='Reds',
        cmin=0,
        cmax=50,
        opacity=0.7,
        colorbar=dict(title="Velocidad (km/h)")
    ),
    name='Puntos de velocidad'
))

# Ajustar layout
fig.update_layout(
    title="Visualización 3D de Elevación y Velocidad",
    scene=dict(
        xaxis_title='Longitud',
        yaxis_title='Latitud',
        zaxis_title='Elevación',
        zaxis=dict(range=[z_min, z_max]),  # Ajustar el rango del eje z
        aspectratio=dict(x=1, y=1, z=0.5)  # Ajustar la relación de aspecto
    ),
    width=1000,
    height=700,
    margin=dict(l=0, r=0, b=0, t=50)
)

# Mostrar la visualización en el navegador
print("Mostrando la visualización en el navegador...")
fig.show(renderer="browser")
