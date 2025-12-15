
"""
Simulacion 01 utilizando dos ego vehicles en el mapa 10 de Carla.
Se conducen de forma automática.
La información se imprime en pantalla.
Solo se almacenan las imágenes y otras renderizaciones como prueba.

@author Mario Martin <martinperezm@unican.es>, CARLA Simulator 
@version 1.0.12-25
"""

import carla

import argparse
import time
import logging
import random

# CONSTANTES
NUM_EGO_VEHICLES = 2
VEHICLE_MODEL = 'vehicle.tesla.model3'
ROLE_NAME = 'ego_'
SENSOR_TICK = 5.0

def spawn_vehicle_with_attached_sensors(world, ego_bp_id, role_name, spawn_point_idx, sensor_configuration):
    ego_bp = world.get_blueprint_library().find(ego_bp_id)
    ego_bp.set_attribute('role_name', role_name)
    ego_color = random.choice(ego_bp.get_attribute('color').recommended_values)
    ego_bp.set_attribute('color', ego_color)
    
    spawn_points = world.get_map().get_spawn_points()
    
    if len(spawn_points) > 0:
        random.shuffle(spawn_points)
        ego_transform = spawn_points[spawn_point_idx]
        ego_vehicle = world.spawn_actor(ego_bp, ego_transform)
        print('\n' + role_name + ' spawned.')
    else: 
        logging.warning('Could not found any spawn points.')

    # Camara RGB
    if sensor_configuration.get('rgb', False):
        cam_bp = None
        cam_bp = world.get_blueprint_library().find('sensor.camera.rgb')
        cam_bp.set_attribute('image_size_x', str(1920))
        cam_bp.set_attribute('image_size_y', str(1080))
        cam_bp.set_attribute('fov', str(105))
        cam_location = carla.Location(2, 0, 1)
        cam_rotation = carla.Rotation(0, 180, 0)
        cam_transform = carla.Transform(cam_location, cam_rotation)
        ego_cam = world.spawn_actor(cam_bp, cam_transform, attach_to = role_name,\
                                    attachment_type = carla.AttachmentType.Rigid)
        ego_cam.listen(lambda image: image.save_to_disk('../recorder/sim_01_dataset/rgb/%.6d.jpg' % image.frame))
    
    # Detector de colisiones
    if sensor_configuration.get("col", False):
        col_bp = world.get_blueprint_library().find('sensor.other.collision')
        col_location = carla.Location(0,0,0)
        col_rotation = carla.Rotation(0,0,0)
        col_transform = carla.Transform(col_location, col_rotation)
        ego_col = world.spawn_actor(col_bp, col_transform, attach_to = role_name,\
                                    attachment_type = carla.AttachmentType.Rigid)
        def col_callback(colli):
            print('Collision detected:\n' + str(colli) + '\n')
        ego_col.listen(lambda colli: col_callback(colli))

    # Invasion de linea
    if sensor_configuration.get("lane", False):
        lane_bp = world.get_blueprint_library().find('sensor.other.lane_invasion')
        lane_location = carla.Location(0, 0, 0)
        lane_rotation = carla.Rotation(0, 0, 0)
        lane_transform = carla.Transform(lane_location, lane_rotation)
        ego_lane = world.spawn_actor(lane_bp, lane_transform, attach_to = role_name,\
                                     attachment_type = carla.AttachmentType.Rigid)
        def lane_callback(lane):
            print('Lane invasion detected:\n' + str(lane) + '\n')
        ego_lane.listen(lambda lane: lane_callback(lane))

    # Obstaculo
    obs_bp = world.get_blueprint_library().find('sensor.other.obstacle')
    obs_bp.set_attribute('only_dinamics', str(True))
    obs_location = carla.Location(0, 0, 0)
    obs_rotation = carla.Rotation(0, 0, 0)
    obs_transform = carla.Transform(obs_location, obs_rotation)
    ego_obs = world.spawn_actor(obs_bp, obs_transform, attach_to = role_name,\
                                attachment_type = carla.AttachmentType.Rigid)
    def obs_callback(obs):
        print('Obstacle detected:\n' + str(obs) + '\n')
    ego_obs.listen(lambda obs: obs_callback(obs))

    # GNSS
    gnss_bp = world.get_blueprint_library().find('sensor.other.gnss')
    gnss_location = carla.Location(0, 0, 0)
    gnss_rotation = carla.Rotation(0, 0, 0)
    gnss_transform = carla.Transform(gnss_location, gnss_rotation)
    gnss_bp.set_attribute('sensor_tick', str(SENSOR_TICK))
    ego_gnss = world.spawn_actor(gnss_bp, gnss_transform, attach_to = role_name,\
                                 attachment_type = carla.AttachmentType.Rigid)
    def gnss_callback(gnss):
        print('GNSS measure: ' + str(gnss) + '\n')
    ego_gnss.listen(lambda gnss: gnss_callback(gnss))
    
    # IMU
    imu_bp = world.get_blueprint_library().find('sensor.other.imu')
    imu_location = carla.Location(0, 0, 0)
    imu_rotation = carla.Rotation(0, 0, 0)
    imu_transform = carla.Transform(imu_location, imu_rotation)
    imu_bp.set_attribuyte('sensor_tick', str(SENSOR_TICK))
    ego_imu = world.spawn_actor(imu_bp, imu_transform, attach_to = role_name,\
                                attachment_type = carla.AttachmentType.Rigid)
    def imu_callback(imu):
        print('IMU measure:\n' + str(imu) + '\n')
    ego_imu.listen(lambda imu: imu_callback(imu))

    # Habilitar piloto automatico
    ego_vehicle.set_autopilot(True)


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

    # Procesado de argumentos
    args = argparser.parse_args()

    # Formato de mensajes de logging (Ej. INFO: "Loreipsum")
    logging.basicConfig(format = '%(levelname)s: %(message)s', level = logging.INFO)

    client = carla.Client(args.host, args.port)
    # Si no se recibe respuesta, las operaciones contra el servidor fallan.
    client.set_timeout(10.0)

    try:
    
        world = client.get_world()
        
        # Configuracion de sensores
        config_ego_1 = {
            'rgb': True,
            'col': True,
            'lane': True,
            'gnss': True,
            'imu': True
        }

        config_ego_2 = {
            'rgb': False,
            'col': False,
            'lane': False,
            'gnss': True,
            'imu': True
        }

        # Blueprint-ID, ROLE_NAME, SPAWN_POINT_INDEX
        vehicle_configs = [
            ('vehicle.tesla.model3', 'ego_1', 0, config_ego_1),
            ('vehicle.audi.a2', 'ego_2', 1, config_ego_2)
        ]

        spawn_points = world.get_map().get_spawn_points()
        random.shuffle(spawn_points)

        # Grabacion de simulacion
        client.start_recorder('../recorder/recording01.log')

        # Crear EGO_VEHICLES
        for i in range(NUM_EGO_VEHICLES):
            # Obtener la plantilla un vehiculo y establecer rol y color
            ego_bp = world.get_blueprint_library().find(VEHICLE_MODEL)
            spawn_vehicle_with_attached_sensors(world, ego_bp, ROLE_NAME + i, spawn_point)
            
            print('\nRole for vehicle ' + i + ' is set.')
            ego_color = random.choice(ego_bp.get_attribute('color').recommended_values)
            ego_bp.set_attribute('color', ego_color)
            print('\NColor for vehicle ' + i + ' is set.')

            spawn_points = world.get_map().get_spawn_points()
            number_of_spawn_points = len(spawn_points)

            if number_of_spawn_points > 0: # Si existen puntos disponibles de spawn
                random.shuffle(spawn_points)
                ego_transform = spawn_points[0]
                ego_vehicle = world.spawn_actor(ego_bp, ego_transform)
                print('\nVehicle ' + i ' is spawned.')
            else:
                logging.warning('Could not found any spawn points.')






