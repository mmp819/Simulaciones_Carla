"""
Simulacion 01 utilizando dos ego vehicles en el mapa 10 de Carla.
Se conducen de forma automática.
La información se recoge en un fichero CSV.

@author Mario Martin <martinperezm@unican.es>, Carla Simulator
@version 1.0.1-26
"""

import carla

import argparse
import logging
import random
import sys

import json
import os
import queue
import time 
from datetime import datetime

# Attributes
IMAGE_SIZE_X = 1280
IMAGE_SIZE_Y = 720
IMAGE_FOV = 105

RGB_LOCATION_X = 2
RGB_LOCATION_Y = 0
RGB_LOCATION_Z = 1

RGB_ROTATION_X = 0
RGB_ROTATION_Y = 180
RGB_ROTATION_Z = 0

SENSOR_TICK = 0.5

# Blueprints IDs
RGB_SENSOR = 'sensor.camera.rgb'
COLLISION_SENSOR = 'sensor.other.collision'
LANE_SENSOR = 'sensor.other.lane_invasion'
OBSTACLE_SENSOR = 'sensor.other.obstacle'
GNSS_SENSOR = 'sensor.other.gnss'
IMU_SENSOR = 'sensor.other.imu'

# Directorios
OUTPUT_DIR = "../recorder/sim_01_datamodel"
IMG_SUBDIR = "rgb_images"

def ask_config(role_name):
    """
    Docstring for ask_config
    
    :param role_name: Description
    """
    print(f"\n--- Configurando sensores para:  {role_name} ---")
    print("Pulsar [S/s] o [Y/y] para activar. Otra tecla para desactivar.")

    config = {}
    sensors = ['rgb', 'collision', 'lane', 'obstacle', 'gnss', 'imu']

    for s in sensors:
        response = input(f"¿Activar {s.upper()}? > ").lower()
        config[s] = response in ['s', 'y']
    return config

def create_camera(world, bp_lib, size_x, size_y, fov, location, rotation, vehicle):
    """
    Docstring for create_camera
    
    :param world: Description
    :param bp_lib: Description
    :param size_x: Description
    :param size_y: Description
    :param fov: Description
    :param location: Description
    :param rotation: Description
    :param vehicle: Description
    """
    cam_bp = bp_lib.find(RGB_SENSOR)

    # Establecer atributos de imagen
    cam_bp.set_attribute('image_size_x', str(size_x))
    cam_bp.set_attribute('image_size_y', str(size_y))
    cam_bp.set_attribute('fov', str(fov))
    
    # Establecer atributos de ubicacion y giro
    cam_transform = carla.Transform(location, rotation)

    # Crear camara
    cam = world.spawn_actor(cam_bp, cam_transform, attach_to = vehicle, \
                            attachment_type = carla.AttachmentType.Rigid)
    
    return cam

def spawn_vehicle_with_attached_sensors(world, ego_bp_id, role_name, spawn_point, sensor_configuration):
    """
    Docstring for spawn_vehicle_with_attached_sensors
    
    :param world: Description
    :param ego_bp_id: Description
    :param role_name: Description
    :param spawn_point: Description
    :param sensor_configuration: Description
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

    ############
    # SENSORES #
    ############

    def push_data(sensor_type, data_payload):
        """
        Docstring for push_data
        
        :param sensor_type: Description
        :param data_payload: Description
        """
        timestamp = datetime.time().isoformat()
        entry = {
            "role": role_name,
            "sensor": sensor_type,
            "timestamp": timestamp,
            "data": data_payload
        }
        data_queue.put(entry)

    # 1. Camara RGB
    if sensor_configuration.get('rgb', False):
        location = carla.Location(RGB_LOCATION_X, RGB_LOCATION_Y, RGB_LOCATION_Z)
        rotation = carla.Rotation(RGB_ROTATION_X, RGB_ROTATION_Y, RGB_ROTATION_Z)
        cam = create_camera(world, blueprint_library, IMAGE_SIZE_X, IMAGE_SIZE_Y, IMAGE_FOV, \
                            location, rotation, vehicle)
        
        def cam_callback(image):
            filename = f"{role_name}_{image.frame:06d}.jpg"
            abs_path = os.path.join(OUTPUT_DIR, IMG_SUBDIR, filename)

            rel_path = os.path.join(IMG_SUBDIR, filename)

            image.save_to_disk(abs_path)

            push_data("rgb", {
                "frame": image.frame,
                "relative_path": rel_path,
                "width": image.width,
                "height": image.height
            })
        
        # Listener: Guardar imagen incluyendo el nombre del vehiculo y el frame
        cam.listen(lambda image: cam_callback(image))
        sensors.append(cam)

    # 2. Detector de colisiones
    if sensor_configuration.get('col', False):
        col_bp = blueprint_library.find(COLLISION_SENSOR)

        col = world.spawn_actor(col_bp, carla.Transform(), attach_to = vehicle, \
                                attachment_type = carla.AttachmentType.Rigid)
        
        # Listener: 
        def col_callback(event):
            other_actor = event.other_actor.type_id
            impulse = event.normal_impulse
            intensity = (impulse.x**2 + impulse.y**2 + impulse.z**2)**0.5

            push_data("collision", {
                "frame": event.frame,
                "other_actor": other_actor,
                "intensity": intensity
            })

        col.listen(lambda event: col_callback(event))
        sensors.append(col)

    # 3. Detector de invasion de lineas
    if sensor_configuration.get('lane', False):
        lane_bp = blueprint_library.find(LANE_SENSOR)

        lane = world.spawn_actor(lane_bp, carla.Transform(), attach_to = vehicle, \
                                 attachment_type = carla.AttachmentType.Rigid)
        
        # Listener: 
        def lane_callback(event):
            text_markings = [str(x.type) for x in event.crossed_lane_markings]
            push_data("lane_invasion", {
                "frame": event.frame,
                "crossed_markings": text_markings
            })
        lane.listen(lambda event: lane_callback(event))
        sensors.append(lane)

    # 4. Obstaculo
    if sensor_configuration.get('obstacle', False):
        obs_bp = blueprint_library.find(OBSTACLE_SENSOR)
        obs_bp.set_attribute('only_dinamics', str(True))

        obs = world.spawn_actor(obs_bp, carla.Transform(), attach_to = vehicle, \
                                attachment_type = carla.AttachmentType.Rigid)
        
        # Listener:
        def obs_callback(event):
            push_data("obstacle", {
                "frame": event.frame,
                "distance": event.distance,
                "other_actor": event.other_actor.type_id
            })
        obs.listen(lambda event: obs_callback(event))
        sensors.append(obs)

    # 5. GNSS
    if sensor_configuration.get('gnss', False):
        gnss_bp = blueprint_library.find(GNSS_SENSOR)
        gnss_bp.set_attribute('sensor_tick', str(SENSOR_TICK))

        gnss = world.spawn_actor(gnss_bp, carla.Transform(), attach_to = vehicle, \
                                 attachment_type = carla.AttachmentType.Rigid)
                                 
        # Listener:
        def gnss_callback(event):
            push_data("gnss", {
                "frame": event.frame,
                "latitude": event.latitude,
                "longitude": event.longitude,
                "altitude": event.altitude
            })
        gnss.listen(lambda event: gnss_callback(event))
        sensors.append(gnss)

    # 6. IMU
    if sensor_configuration.get('imu', False):
        imu_bp = blueprint_library.find(IMU_SENSOR)
        imu_bp.set_attribute('sensor_tick', str(SENSOR_TICK))

        imu = world.spawn_actor(imu_bp, carla.Transform(), attach_to = vehicle, \
                                attachment_type = carla.AttachmentType.Rigid)
        
        # Listener
        def imu_callback(imu):
            TODO
        imu.listen(lambda imu: imu_callback(imu))
        sensors.append(imu)
    
    return vehicle, sensors

def main():
    # Definicion de argumentos
    argparser = argparse.ArgumentParser(
        description = __doc__
    )
    
    # IP del servidor que ejecuta CARLA
    argparser.add_argument(
        '--host',
        metavar = 'H',
        default = '127.0.0.1'
        help = 'IP of the host server (default: 127.0.0.1)'
    )
    # Puerto del servidor que ejecuta CARLA
    argparser.add_argument(
        '-p', '--port',
        metavar = 'P',
        default = 2000
        type = int,
        help = 'TCP port to listen to (default: 2000)'
    )

    # Procesado de argumentos
    args = argparser.parse_args()

    # Formato de mensajes de logging (Ej. INFO: "Loreipsum")
    logging.basicConfig(format = '%(levelname)s: %(message)s', level = logging.INFO)

    client = carla.Client(args.host, args.port)
    # Si no se recibe respuesta, las operaciones fallan
    client.set_timeout(10.0)

    vehicles = []

    try:
        world = client.get_world()

        client.start_recorder('../recorder/sim_01_datamodel/recording01.log')

        config_ego_1 = {
            'rgb': True,
            'col': True,
            'lane': True,
            'obstacle': True,
            'gnss': True,
            'imu': True
        }

        config_ego_2 = {
            'rgb': False,
            'col': False,
            'lane': False,
            'obstacle': False,
            'gnss': True,
            'imu': True
        }
        
        vehicle_configs = [
            {'vehicle.tesla.model3', 'ego_1', 0, config_ego_1},
            {'vehicle.audi.a2', 'ego_2', 1, config_ego_2}
        ]

        spawn_points = world.get_map().get_spawn_points()
        random.shuffle(spawn_points)

        # Crear vehiculos
        for blueprint_id, role_name, spawn_index, sensor_config in vehicle_configs:
            if spawn_index < len(spawn_points):
                spawn_point = spawn_points[spawn_index]
                vehicle, sensors = spawn_vehicle_with_attached_sensors(
                    world,
                    blueprint_id,
                    role_name,
                    spawn_point,
                    sensor_config
                )

                if vehicle:
                    vehicles.append(vehicle)
                    vehicles.extend(sensors)

            else:
                logging.warning('No hay suficientes puntos de spawn para ' + role_name)
        
        for vehicle in vehicles:
            vehicle.set_autopilot(True)
        
        while True:
            world.wait_for_tick()
    
    finally:
        print('\nDeteniendo grabacion...')
        client.stop_recorder()

        # Limpieza de vehiculos del simulador
        if vehicles:
            client.apply_batch([carla.command.DestroyActor(v) for v in vehicles])
            print('\nVehiculos eliminados.')
        else:
            print('\nNo hay vehiculos por eliminar.')

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit()
    except Exception as e:
        print('\nError inesperado: ' + str(e))
    finally:
        print('\nSimulacion 01 de CARLA terminada.')