"""
Simulacion 01 utilizando dos ego vehicles en el mapa 10 de Carla.
Se conducen de forma automática.
La información se recoge en un fichero JSON.

@author Mario Martin <martinperezm@unican.es>, Carla Simulator
@version 1.2.0
"""

import carla

import argparse
import logging
import random
import json
import os
import queue
import time 
from datetime import datetime

##############################
# --- CONFIGURACION GLOBAL ---
##############################

# Atributos de imagen
IMAGE_SIZE_X = 1280
IMAGE_SIZE_Y = 720
IMAGE_FOV = 105

# Atributos de camara RGB
RGB_LOCATION_X = 2
RGB_LOCATION_Y = 0
RGB_LOCATION_Z = 1
RGB_ROTATION_X = 0
RGB_ROTATION_Y = 0
RGB_ROTATION_Z = 0

# Atributos de LiDAR
LIDAR_LOCATION_X = 0
LIDAR_LOCATION_Y = 0
LIDAR_LOCATION_Z = 2

# Atributos de Radar
RADAR_LOCATION_X = 2
RADAR_LOCATION_Y = 0
RADAR_LOCATION_Z = 1
RADAR_PITCH = 5

# Ticks
SENSOR_TICK = 0.5
WORLD_TICK = 0.05
FRAME_TOLERANCE = 2

# Blueprints
RGB_SENSOR = "sensor.camera.rgb"
COLLISION_SENSOR = "sensor.other.collision"
LANE_SENSOR = "sensor.other.lane_invasion"
OBSTACLE_SENSOR = "sensor.other.obstacle"
GNSS_SENSOR = "sensor.other.gnss"
IMU_SENSOR = "sensor.other.imu"
LIDAR_SENSOR = "sensor.lidar.ray_cast"
RADAR_SENSOR = "sensor.other.radar"
SEMANTIC_LIDAR_SENSOR = "sensor.lidar_ray_cast_semantic"

# Directorios
OUTPUT_DIR = "../recorder/sim_01_datamodel"
IMG_SUBDIR = "rgb_images"
LIDAR_SUBDIR = "lidar_clouds"

# Conversiones
MS_TO_KMH = 3.6

class SimulationLogger:
    """
    Clase estática encargada del procesamiento, agrupación y guardado de datos
    recopilados en una simulación de CARLA. Se almacenan en formato JSON.
    """

    @staticmethod
    def save_session(simulation_log, base_configs):
        """
        Procesa la cola de datos generados en la simulación y genera un fichero
        JSON para cada vehículo.

        Parameters:
            simulation_log (list): Lista de diccionarios con los eventos capturados.
            base_configs (list): Configuracion inicial de vehiculos.
        """

        print("\nProcesando y guardando datos...")

        if not simulation_log:
            print("Sin datos para guardar.")
            return
        
        # Identificar todos los roles (vehiculos) que han generado datos
        unique_roles = set(entry["role"] for entry in simulation_log)
        if not unique_roles:
            unique_roles = [cfg[1] for cfg in base_configs]

        for role in unique_roles:
            SimulationLogger.__process_role_data(role, simulation_log)

    @staticmethod
    def __process_role_data(role, full_log):
        """
        Filtra, agrupa y guarda los datos de un vehículo concreto.
        
        Parameters:
            role (str): Rol o identificador del vehículo (ej: "ego_1").
            full_log (list): Log completo de todos los vehículos de la simulación.
        """

        # Filtrar datos correspondientes al vehiculo "role"
        raw_data = [d for d in full_log if d["role"] == role]
        if not raw_data:
            return
        
        grouped_data = {}

        for entry in raw_data:
            frame_id = entry["data"]["frame"]
            sensor_type = entry["sensor"]

            # Agrupacion con cierta tolerancia para frames cercanos.
            target_frame = None
            for existing_frame in grouped_data.keys():
                if abs(existing_frame - frame_id) <= FRAME_TOLERANCE:
                    target_frame = existing_frame
                    break

            # Si no existe un grupo para el frame, se crea uno nuevo.
            if target_frame is None:
                target_frame = frame_id
                grouped_data[target_frame] = {
                    "frame": target_frame,
                    "timestamp": entry["timestamp"],
                    "sensors": {}
                }

            grouped_data[target_frame]["sensors"][sensor_type] = entry["data"]
        
        # Ordenar en orden de generación
        sorted_data = sorted(grouped_data.values(), key = lambda x: x["frame"])

        # Definir directorio y guardar
        role_dir = os.path.join(OUTPUT_DIR, role)
        os.makedirs(role_dir, exist_ok=True)
        json_path = os.path.join(role_dir, "simulation_log.json")

        try:
            with open(json_path, "w") as f:
                json.dump(sorted_data, f, indent = 4)
            print(f"Log guardado: {json_path}")
        except Exception as e:
            print(f"Error guardando {role}: {e}")



class BusSensor:
    """
    Clase que representa un sensor virtual o ficticio, encargado de extraer
    telemetría del vehículo con datos similares a los que puede haber en un CAN Bus.
    """

    def __init__(self, world, vehicle, role_name, data_queue):
        """
        Inicializa la clase.
        
        Parameters:
            world (carla.World): Instancia del mundo donde se ejecuta la simulación de CARLA.
            vehicle (carla.Vehicle): Actor de tipo vehículo que se quiere monitorizar.
            role_name (str): Identificador/rol asignado al vehículo.
            data_queue (queue.Queue): Cola compartida para el envío de datos.
        """

        self.world = world
        self.vehicle = vehicle
        self.role_name = role_name
        self.data_queue = data_queue
        self.sensor_id = self.world.on_tick(self.tick)
    
    def tick(self, world_snapshot):
        """
        Callback ejecutado en cada tick de la simulación. Extrae datos relativos a las físicas
        y la lógica del vehículo.

        Parameters:
            world_snapshot (carla.WorldSnapshot): Captura del estado del mundo para un frame concreto.
        """

        try:
            # Buscar el snapshot de un vehículo concreto
            actor_snapshot = world_snapshot.find(self.vehicle.id)
            if actor_snapshot is None:
                return

            # Físicas del vehículo. Incluida en el snapshot de actores.
            velocity = actor_snapshot.get_velocity()
            acceleration = actor_snapshot.get_acceleration()
            angular_velocity = actor_snapshot.get_angular_velocity()

            speed_ms = (velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2) ** 0.5
            speed_kmh = speed_ms * MS_TO_KMH
            
            # Lógica obtenida directamente del actor de tipo vehiculo.
            control = self.vehicle.get_control()
            speed_limit = self.vehicle.get_speed_limit()
            light_state = self.vehicle.get_light_state()
            lights = {
                "raw": light_state,
                "none": bool(light_state & carla.VehicleLightState.NONE),
                "position": bool(light_state & carla.VehicleLightState.Position),
                "low_beam": bool(light_state & carla.VehicleLightState.LowBeam),
                "high_beam": bool(light_state & carla.VehicleLightState.HighBeam),
                "brake": bool(light_state & carla.VehicleLightState.Brake),
                "right_blinker": bool(light_state & carla.VehicleLightState.RightBlinker),
                "left_blinker": bool(light_state & carla.VehicleLightState.LeftBlinker),
                "reverse": bool(light_state & carla.VehicleLightState.Reverse),
                "fog": bool(light_state & carla.VehicleLightState.Fog),
                "interior": bool(light_state & carla.VehicleLightState.Interior),
                "all": bool(light_state & carla.VehicleLightState.All)
            }

            data = {
                "frame": world_snapshot.frame,
                #"timestamp": world_snapshot.timestamp.platform_timestamp,
                "physics": {
                    "speed_ms": speed_ms,
                    "speed_kmh": speed_kmh,
                    "acceleration": {"x": acceleration.x, "y": acceleration.y, "z": acceleration.z},
                    "angular_velocity": {"x": angular_velocity.x, "y": angular_velocity.y, "z": angular_velocity.z}
                },
                "control": {
                    "steer": control.steer,
                    "throttle": control.throttle,
                    "brake": control.brake,
                    "gear": control.gear,
                    "hand_brake": control.hand_brake,
                    "reverse": control.reverse,
                    "lights": lights,
                    "speed_limit": speed_limit
                }
            }

            entry = {
                "role": self.role_name,
                "sensor": "bus",
                "timestamp": datetime.now().isoformat(),
                "data": data
            }

            self.data_queue.put(entry)
        
        except Exception as e:
            logging.error(f"Error en Bus: {e}")
    
    def destroy(self):
        """
        Elimina el registro del callback para que no haya problemas o errores en el cierre.
        """

        if self.sensor_id:
            self.world.remove_on_tick(self.sensor_id)
            self.sensor_id = None

class SensorFactory:
    """
    Clase que incluye los métodos necesarios para instanciar y configurar sensores de los vehículos.
    """

    def __init__(self, world, vehicle, role_name, data_queue):
        """
        Inicializa la clase.
        
        Parameters:
            world (carla.World): Instancia del mundo donde se ejecuta la simulación de CARLA.
            vehicle (carla.Vehicle): Actor de tipo vehículo que se quiere monitorizar.
            role_name (str): Identificador/rol asignado al vehículo.
            data_queue (queue.Queue): Cola compartida para el envío de datos.
        """

        self.world = world
        self.bp_lib = world.get_blueprint_library()
        self.vehicle = vehicle
        self.role = role_name
        self.queue = data_queue
        self.tick_str = str(SENSOR_TICK)

    def _push(self, sensor_type, payload):
        """
        Método que agrupa la lógica necesaria para el envío de datos estandarizados a la cola.
        
        Parameters:
            sensor_type (str): Tipo de sensor del que se enviarán datos.
            payload: Datos recogidos por el sensor.
        """

        self.queue.put({
            "role": self.role,
            "sensor": sensor_type,
            "timestamp": datetime.now().isoformat(),
            "data": payload
        })

    def spawn_rgb (self):
        """
        Genera una cámara RGB y guarda las imágenes en formato jpg.

        Returns:
            carla.Sensor: RGB Camera
        """

        bp = self.bp_lib.find(RGB_SENSOR)
        bp.set_attribute("image_size_x", str(IMAGE_SIZE_X))
        bp.set_attribute("image_size_y", str(IMAGE_SIZE_Y))
        bp.set_attribute("fov", str(IMAGE_FOV))
        bp.set_attribute("sensor_tick", self.tick_str)

        trans = carla.Transform(carla.Location(RGB_LOCATION_X, RGB_LOCATION_Y, RGB_LOCATION_Z),
                                carla.Rotation(RGB_ROTATION_X, RGB_ROTATION_Y, RGB_ROTATION_Z))
        cam = self.world.spawn_actor(bp, trans, attach_to = self.vehicle, 
                                     attachment_type = carla.AttachmentType.Rigid)

        def callback(image):
            fname = f"{image.frame:06d}.jpg"
            rel_path = os.path.join(IMG_SUBDIR, fname)
            abs_path = os.path.join(OUTPUT_DIR, self.role, rel_path)
            image.save_to_disk(abs_path)
            self._push("rgb", {"frame": image.frame,
                               "relative_path": rel_path})
        
        cam.listen(callback)
        return cam
    
    def spawn_lidar(self):
        """
        Genera un LiDAR y guarda las nubes de puntos en formato ply.

        Returns:
            carla.Sensor: LiDAR Raycast
        """

        bp = self.bp_lib.find(LIDAR_SENSOR)
        bp.set_attribute("sensor_tick", self.tick_str)

        trans = carla.Transform(carla.Location(LIDAR_LOCATION_X, LIDAR_LOCATION_Y, LIDAR_LOCATION_Z))
        lidar = self.world.spawn_actor(bp, trans, attach_to = self.vehicle, \
                                  attachment_type = carla.AttachmentType.Rigid)
        
        def callback(point_cloud):
            fname = f"{point_cloud.frame:06d}.ply"
            rel_path = os.path.join(LIDAR_SUBDIR, fname)
            abs_path = os.path.join(OUTPUT_DIR, self.role, rel_path)
            point_cloud.save_to_disk(abs_path)
            self._push("lidar", {"frame": point_cloud.frame,
                                 "relative_path": rel_path,
                                 "num_points": len(point_cloud),
                                 "horizontal_angle": point_cloud.horizontal_angle})

        lidar.listen(callback)
        return lidar
    
    def spawn_gnss(self):
        """
        Genera un sensor GNSS (métricas GPS).

        Returns:
            carla.Sensor: GNSS
        """

        bp = self.bp_lib.find(GNSS_SENSOR)
        bp.set_attribute("sensor_tick", self.tick_str)
        gnss = self.world.spawn_actor(bp, carla.Transform(), attach_to = self.vehicle, \
                                      attachment_type = carla.AttachmentType.Rigid)

        def callback(data):
            self._push("gnss", {
                "frame": data.frame,
                "latitude": data.latitude,
                "longitude": data.longitude,
                "altitude": data.altitude
            })
                                 
        gnss.listen(callback)
        return gnss
    
    def spawn_radar(self):
        """
        Genera un radar y procesa posibles detecciones.

        Returns:
            carla.Sensor: Radar
        """

        bp = self.bp_lib.find(RADAR_SENSOR)
        bp.set_attribute("sensor_tick", self.tick_str)
        trans = carla.Transform(carla.Location(RADAR_LOCATION_X, RADAR_LOCATION_Y, RADAR_LOCATION_Z),
                                carla.Rotation(pitch = RADAR_PITCH))
        radar = self.world.spawn_actor(bp, trans, attach_to = self.vehicle, \
                                       attachment_type = carla.AttachmentType.Rigid)
        
        def callback(data):
            points = []
            for detection in data:
                points.append({
                    "velocity": detection.velocity,
                    "azimuth": detection.azimuth,
                    "altitude": detection.altitude,
                    "depth": detection.depth
                })

                self._push("radar", {
                    "frame": data.frame,
                    "num_detections": len(points),
                    "detections": points
                })

        radar.listen(callback)
        return radar
    
    def spawn_collision_detector(self):
        """
        Genera un detector de colisiones con otros objetos o vehículos.

        Returns:
            carla.Sensor: Collision detector.
        """

        bp = self.bp_lib.find(COLLISION_SENSOR)
        collision_sensor = self.world.spawn_actor(bp, carla.Transform(), attach_to = self.vehicle, \
                                             attachment_type = carla.AttachmentType.Rigid)

        def callback(collision):
            impulse = collision.normal_impulse
            intensity = (impulse.x ** 2 + impulse.y ** 2 + impulse.z ** 2) ** 0.5

            self._push("collision", {
                "frame": collision.frame,
                "intensity": intensity,
                "other_actor": collision.other_actor.type_id
            })
        
        collision_sensor.listen(callback)
        return collision_sensor
    
    def spawn_lane_invasion_detector(self):
        """
        Genera un detector de cruce de líneas de un carril.

        Returns:
            carla.Sensor: Lane invasion detector.
        """

        bp = self.bp_lib.find(LANE_SENSOR)
        lane_sensor = self.world.spawn_actor(bp, carla.Transform(), attach_to = self.vehicle, \
                                             attachment_type = carla.AttachmentType.Rigid)
        
        def callback(invasion):
            text_markings = [str(x.type) for x in invasion.crossed_lane_markings]
            self._push("lane_invasion", {
                "frame": invasion.frame,
                "crossed_markings": text_markings
            })

        lane_sensor.listen(callback)
        return lane_sensor
    
    def spawn_obstacle_detector(self):
        """
        Genera un detector de obstáculos en frente de un vehículo.

        Returns:
            carla.Sensor: Obstacle detector
        """

        bp = self.bp_lib.find(OBSTACLE_SENSOR)
        obstacle_sensor = self.world.spawn_actor(bp, carla.Transform(), attach_to = self.vehicle, \
                                                 attachment_type = carla.AttachmentType.Rigid)
        
        def callback(detection):
            self._push("obstacle", {
                "frame": detection.frame,
                "distance": detection.distance,
                "other_actor": detection.other_actor.type_id,
            })
        
        obstacle_sensor.listen(callback)
        return obstacle_sensor
    
    def spawn_imu(self):
        """
        Genera IMU (Acelerómetro + Giroscopio + Brújula).

        Returns:
            carla.Sensor: IMU
        """

        bp = self.bp_lib.find(IMU_SENSOR)
        bp.set_attribute("sensor_tick", str(SENSOR_TICK))
        imu = self.world.spawn_actor(bp, carla.Transform(), attach_to = self.vehicle, \
                                     attachment_type = carla.AttachmentType.Rigid)
        
        def callback(metrics):
            self._push("imu", {
                "frame": metrics.frame,
                "accelerometer": {"x": metrics.accelerometer.x, "y": metrics.accelerometer.y, "z": metrics.accelerometer.z},
                "gyroscope": {"x": metrics.gyroscope.x, "y": metrics.gyroscope.y, "z": metrics.gyroscope.z},
                "compass": metrics.compass
            })

        imu.listen(callback)
        return imu


def prepare_directories(role_name):
    """
    Crea la estructura de carpetas necesaria para el guardado de datos más pesados,
    como el LiDAR o imágens RGB.

    Parameters:
        role_name (str): Nombre o identificador del vehículo, para la creación de sus
                        subcarpetas.
    """

    base = os.path.join(OUTPUT_DIR, role_name)
    os.makedirs(os.path.join(base, IMG_SUBDIR), exist_ok = True)
    os.makedirs(os.path.join(base, LIDAR_SUBDIR), exist_ok = True)

def spawn_ego_vehicle(world, bp_id, role_name, spawn_point, config, queue):
    """
    Crea un vehículo, configura sus sensores y activa su conducción en piloto automático.

    Parameters:
        world: Instancia del mundo de la simulación en CARLA.
        bp_id: ID del blueprint del vehículo.
        role_name: Nombre o identificador del vehículo.
        spawn_point: Ubicación inicial o de creación del vehículo en el mapa.
        config: Diccionario con flags booleanos que indican los sensores a crear.
        queue: Cola de mensajes.

    Returns:
        tuple: (carla.Vehicle: Vehicle, list: List of Sensors Attached)
    """

    bp_lib = world.get_blueprint_library()
    v_bp = bp_lib.find(bp_id)
    v_bp.set_attribute("role_name", role_name)

    vehicle = world.try_spawn_actor(v_bp, spawn_point)
    if not vehicle:
        return None, []
    
    factory = SensorFactory(world, vehicle, role_name, queue)
    sensors = []

    if config.get("rgb"):
        sensors.append(factory.spawn_rgb())
    
    if config.get("collision"):
        sensors.append(factory.spawn_collision_detector())
    
    if config.get("lane"):
        sensors.append(factory.spawn_lane_invasion_detector())
    
    if config.get("obstacle"):
        sensors.append(factory.spawn_obstacle_detector())

    if config.get("gnss"):
        sensors.append(factory.spawn_gnss())
    
    if config.get("imu"):
        sensors.append(factory.spawn_imu())

    if config.get("lidar"):
        sensors.append(factory.spawn_lidar())
    
    if config.get("radar"):
        sensors.append(factory.spawn_radar())

    if config.get("bus"):
        sensors.append(BusSensor(world, vehicle, role_name, queue))

    return vehicle, sensors

def ask_config(role_name):
    """
    Solicita al usuario los ajustes que deben aplicarse a los sensores de un
    vehiculo de la simulacion.
    Retorna la configuracion de dichos sensores.
    
    Parameters:
        role_name (str): Nombre asignado a un ego_vehicle.

    Returns:
        dict: Diccionario con la configuración en flags de los sensores.
    """

    print(f"\n--- Configurando sensores para:  {role_name} ---")
    print("Pulsar [S/s] o [Y/y] para activar. Otra tecla para desactivar.")

    config = {}
    sensors = ['rgb', 'collision', 'lane', 'obstacle', 'gnss', 'imu', 'lidar', 'radar', 'bus']

    for s in sensors:
        response = input(f"¿Activar {s.upper()}? > ").lower()
        config[s] = response in ['s', 'y']
    return config

def main():
    # Definicion de argumentos
    argparser = argparse.ArgumentParser(
        description = __doc__
    )
    
    # IP del servidor que ejecuta CARLA
    argparser.add_argument(
        '--host',
        metavar = 'H',
        default = '127.0.0.1',
        help = 'IP of the host server (default: 127.0.0.1)'
    )
    # Puerto del servidor que ejecuta CARLA
    argparser.add_argument(
        '-p', '--port',
        metavar = 'P',
        default = 2000,
        type = int,
        help = 'TCP port to listen to (default: 2000)'
    )

    args = argparser.parse_args()

    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)

    sensor_queue = queue.Queue()
    vehicles = []

    base_configs = [("vehicle.tesla.model3", "ego_1", 0),
                    ("vehicle.audi.a2", "ego_2", 1)]
    
    try:
        world = client.get_world()
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = WORLD_TICK
        world.apply_settings(settings)

        # Preparar vehiculos
        spawn_points = world.get_map().get_spawn_points()
        random.shuffle(spawn_points)

        for bp_id, role, vehicle_id in base_configs:
            prepare_directories(role)
            config = ask_config(role)

            vehicle, sensors = spawn_ego_vehicle(world, bp_id, role, spawn_points[vehicle_id], config, sensor_queue)
            if vehicle:
                vehicles.append(vehicle)
                vehicles.extend(sensors)
                vehicle.set_autopilot(True)
                print(f"Creado: {role}")
        
        print("\nSimulacion iniciada... Pulsar Ctrl+C para finalizar y guardar.")

        # Bucle de ejecucion
        data_log = []
        while True:
            world.tick()
            while not sensor_queue.empty():
                data_log.append(sensor_queue.get_nowait())
            time.sleep(WORLD_TICK)
    
    except KeyboardInterrupt:
        print("\nDeteniendo...")
    
    finally:
        # Guardado y limpieza
        SimulationLogger.save_session(data_log, base_configs)

        print("Limpiando actores...")
        for v in vehicles:
            if hasattr(v, "destroy"):
                v.destroy() # BusSensor
            elif hasattr(v, "id"):
                client.apply_batch([carla.command.DestroyActor(v)]) # Actores estandar de carla

if __name__ == "__main__":
    main()