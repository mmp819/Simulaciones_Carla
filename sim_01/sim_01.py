"""
Simulacion 01 utilizando dos ego vehicles en el mapa 10 de Carla.
Se conducen de forma automática.
La información se recoge en un fichero JSON.

@author Mario Martin <martinperezm@unican.es>, Carla Simulator
@version 1.0.1-26
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

# TICKS
SENSOR_TICK = 0.5
WORLD_TICK = 0.05
FRAME_TOLERANCE = 2

# BLUEPRINTS
RGB_SENSOR = "sensor.camera.rgb"
COLLISION_SENSOR = "sensor.other.collision"
LANE_SENSOR = "sensor.other.lane_invasion"
OBSTACLE_SENSOR = "sensor.other.obstacle"
GNSS_SENSOR = "sensor.other.gnss"
IMU_SENSOR = "sensor.other.imu"
LIDAR_SENSOR = "sensor.lidar.ray_cast"
RADAR_SENSOR = "sensor.other.radar"
SEMANTIC_LIDAR_SENSOR = "sensor.lidar_ray_cast_semantic"

# DIRECTORIOS
OUTPUT_DIR = "../recorder/sim_01_datamodel"
IMG_SUBDIR = "rgb_images"
LIDAR_SUBDIR = "lidar_clouds"

# CONVERSIONES
MS_TO_KMH = 3.6

class SimulationLogger:
    """
    Docstring for SimulationLogger
    """

    @staticmethod
    def save_session(simulation_log, base_configs):
        print("\nProcesando y guardando datos...")

        if not simulation_log:
            print("Sin datos para guardar.")
            return
        
        unique_roles = set(entry["role"] for entry in simulation_log)
        if not unique_roles:
            unique_roles = [cfg[1] for cfg in base_configs]

        for role in unique_roles:
            SimulationLogger.__process_role_data(role, simulation_log)

    @staticmethod
    def __process_role_data(role, full_log):
        raw_data = [d for d in full_log if d["role"] == role]
        if not raw_data:
            return
        
        grouped_data = {}

        for entry in raw_data:
            frame_id = entry["data"]["frame"]
            sensor_type = entry["sensor"]

            # Agrupacion con margenes de frames
            target_frame = None
            for existing_frame in grouped_data.keys():
                if abs(existing_frame - frame_id) <= FRAME_TOLERANCE:
                    target_frame = existing_frame
                    break

            if target_frame is None:
                target_frame = frame_id
                grouped_data[target_frame] = {
                    "frame": target_frame,
                    "timestamp": entry["timestamp"],
                    "sensors": {}
                }

            grouped_data[target_frame]["sensors"][sensor_type] = entry["data"]
        
        sorted_data = sorted(grouped_data.values(), key = lambda x: x["frame"])

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
    def __init__(self, world, vehicle, role_name, data_queue):
        self.world = world
        self.vehicle = vehicle
        self.role_name = role_name
        self.data_queue = data_queue
        self.sensor_id = self.world.on_tick(self.tick)
    
    def tick(self, world_snapshot):
        try:
            actor_snapshot = world_snapshot.find(self.vehicle.id)
            if actor_snapshot is None:
                return

            # Fisica del vehiculo
            velocity = actor_snapshot.get_velocity()
            acceleration = actor_snapshot.get_acceleration()
            angular_velocity = actor_snapshot.get_angular_velocity()
            speed_ms = (velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2) ** 0.5
            speed_kmh = speed_ms * MS_TO_KMH
            
            # Logica
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
                "phyhics": {
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
        if self.sensor_id:
            self.world.remove_on_tick(self.sensor_id)
            self.sensor_id = None

class SensorFactory:
    """
    Docstring for SensorFactory
    """

    def __init__(self, world, vehicle, role_name, data_queue):
        self.world = world
        self.bp_lib = world.get_blueprint_library()
        self.vehicle = vehicle
        self.role = role_name
        self.queue = data_queue
        self.tick_str = str(SENSOR_TICK)

    def _push(self, sensor_type, payload):
        self.queue.put({
            "role": self.role,
            "sensor": sensor_type,
            "timestamp": datetime.now().isoformat(),
            "data": payload
        })

    def spawn_rgb (self):
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
        bp = self.bp_lib.find(IMU_SENSOR)
        bp.set_attribute("sensor_tick", str(SENSOR_TICK))
        imu = self.world.spawn_actor(bp, carla.Transform(), attach_to = self.vehicle, \
                                     attachment_type = carla.AttachmentType.Rigid)
        
        def callback(metrics):
            self._push("metrics", {
                "frame": metrics.frame,
                "accelerometer": {"x": metrics.accelerometer.x, "y": metrics.accelerometer.y, "z": metrics.accelerometer.z},
                "gyroscope": {"x": metrics.gyroscope.x, "y": metrics.gyroscope.y, "z": metrics.gyroscope.z},
                "compass": metrics.compass
            })

        imu.listen(callback)
        return imu


def prepare_directories(role_name):
    base = os.path.join(OUTPUT_DIR, role_name)
    os.makedirs(os.path.join(base, IMG_SUBDIR), exist_ok = True)
    os.makedirs(os.path.join(base, LIDAR_SUBDIR), exist_ok = True)

def spawn_ego_vehicle(world, bp_id, role_name, spawn_point, config, queue):
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
    
    :param role_name: Nombre asignado a un ego_vehicle.
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

def spawn_vehicle_with_attached_sensors(world, ego_bp_id, role_name, spawn_point, sensor_configuration, data_queue):
    """
    Crea un vehiculo junto con sus sensores y lo publica en el entorno de la simulacion.
    
    :param world: Entorno de simulacion.
    :param ego_bp_id: ID del blueprint asociado al modelo de vehiculo.
    :param role_name: Nombre identificativo para el ego_vehicle a crear.
    :param spawn_point: Punto de spawn dentro del mapa existente.
    :param sensor_configuration: Configuracion de sensores a aplicar.
    :param data_queue: Cola para publicacion de datos del JSON.
    """
    sensors = []
    blueprint_library = world.get_blueprint_library()

    # Establecer blueprint del vehiculo
    vehicle_bp = blueprint_library.find(ego_bp_id)
    vehicle_bp.set_attribute('role_name', role_name)

    # Color aleatorio dentro de las posibilidades del BP
    try:
        if 'color' in vehicle_bp.get_attribute('color').recommended_values:
            vehicle_color = random.choice(vehicle_bp.get_attribute('color').recommended_values)
            vehicle_bp.set_attribute('color', vehicle_color)
    except AttributeError:
        pass

    # Crear vehiculo
    vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)

    if vehicle is None:
        logging.warning('Error al crear el vehiculo: ' + role_name)
        return None, []
    
    print('\n' + role_name + 'creado.')

def main():

    # Formato de mensajes de logging (Ej. INFO: "Loreipsum")
    logging.basicConfig(format = '%(levelname)s: %(message)s', level = logging.INFO)

    # Cola de recepcion de datos de los sensores
    sensor_queue = queue.Queue()

    client = carla.Client(args.host, args.port)

    # Si no se recibe respuesta, las operaciones fallan
    client.set_timeout(10.0)

    vehicles = []
    base_configs = [
            ('vehicle.tesla.model3', 'ego_1', 0),
            ('vehicle.audi.a2', 'ego_2', 1)]

    try:
        world = client.get_world()
        settings = world.get_settings()
        settings.synchronous_mode = True       
        settings.fixed_delta_seconds = WORLD_TICK
        world.apply_settings(settings)

        # Ajustar la configuracion de los vehiculos
        spawn_data = []
        for blueprint_id, role_name, vehicle_id in base_configs:
            # Crear carpeta de imagenes RGB
            vehicle_path_img = os.path.join(OUTPUT_DIR, role_name, IMG_SUBDIR)
            if not os.path.exists(vehicle_path_img):
                os.makedirs(vehicle_path_img)

            # Crear carpeta de nubes de puntos LiDAR
            vehicle_path_lidar = os.path.join(OUTPUT_DIR, role_name, LIDAR_SUBDIR)
            if not os.path.exists(vehicle_path_lidar):
                os.makedirs(vehicle_path_lidar)

            config = ask_config(role_name)
            spawn_data.append((blueprint_id, role_name, vehicle_id, config))

        # Obtener puntos de spawn aleatorios
        spawn_points = world.get_map().get_spawn_points()
        random.shuffle(spawn_points)

        # Crear vehiculos
        for blueprint_id, role_name, spawn_index, sensor_config in spawn_data:
            if spawn_index < len(spawn_points):
                spawn_point = spawn_points[spawn_index]
                vehicle, sensors = spawn_vehicle_with_attached_sensors(
                    world,
                    blueprint_id,
                    role_name,
                    spawn_point,
                    sensor_config,
                    sensor_queue
                )

                if vehicle:
                    vehicles.append(vehicle)
                    vehicles.extend(sensors)
                    vehicle.set_autopilot(True)

            else:
                logging.warning(f"No hay suficientes puntos de spawn para {role_name}")
        
        print("\nSimulacion iniciada... Pulsar Ctrl+C para finalizar y guardar.")
        
        # Lista de datos acumulados para fichero JSON
        simulation_data_log = []

        while True:
            world.tick()

            while not sensor_queue.empty():
                try:
                    event = sensor_queue.get_nowait()
                    simulation_data_log.append(event)
                except queue.Empty:
                    break
            
            time.sleep(WORLD_TICK)

    
    finally:
        print('\nDeteniendo grabacion y limpiando...')

        if 'simulation_data_log' in locals() and len(simulation_data_log) > 0:
            unique_roles = set(entry['role'] for entry in simulation_data_log)
            
            if not unique_roles: 
                unique_roles = [cfg[1] for cfg in base_configs]

            for role in unique_roles:
                # Filtrar datos para vehículo con el nombre 'role'
                raw_role_data = [d for d in simulation_data_log if d['role'] == role]
                
                if raw_role_data:
                    # Agrupar por Frame
                    grouped_data = {}
                    
                    for entry in raw_role_data:
                        frame_id = entry['data']['frame']
                        sensor_type = entry['sensor']
                        
                        target_frame = None
                        
                        # 1. Buscar si ya existe un frame dentro del rango de tolerancia
                        for existing_frame in grouped_data.keys():
                            if abs(existing_frame - frame_id) <= FRAME_TOLERANCE:
                                target_frame = existing_frame
                                break
                        
                        # 2. Si no hay ninguno cerca, creamos uno nuevo
                        if target_frame is None:
                            target_frame = frame_id
                            grouped_data[target_frame] = {
                                "frame": target_frame,
                                "timestamp": entry['timestamp'], 
                                "sensors": {}
                            }
                        
                        # Añadir la info del sensor al frame
                        # Si hay múltiples eventos del mismo tipo (ej. 2 colisiones en 1 frame),
                        # se podría convertir en lista. Para RGB/GNSS/IMU es 1 por frame.
                        grouped_data[target_frame]["sensors"][sensor_type] = entry['data']

                    # Convertir a lista ordenada por frame para el JSON
                    # Esto crea un array de objetos, donde cada objeto es una "muestra" completa
                    sorted_final_data = sorted(grouped_data.values(), key=lambda x: x['frame'])

                    # Guardar
                    role_dir = os.path.join(OUTPUT_DIR, role)
                    if not os.path.exists(role_dir):
                        os.makedirs(role_dir, exist_ok=True)
                        
                    json_path = os.path.join(role_dir, 'simulation_log.json')
                    
                    try:
                        with open(json_path, 'w') as f:
                            json.dump(sorted_final_data, f, indent=4)
                        print(f"Log agrupado guardado para {role}: {json_path}")
                    except Exception as e:
                        print(f"Error al guardar log de {role}: {e}")
        else:
            print("No se recogieron datos para guardar.")

        # Limpieza de vehiculos del simulador
        if vehicles:
            for v in vehicles:
                if hasattr(v, "destroy"):
                    v.destroy()
                elif hasattr(v, "id"):
                    client.apply_batch([carla.command.DestroyActor(v)])

if __name__ == '__main__':
    main()