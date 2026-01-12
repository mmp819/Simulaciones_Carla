"""
Simulacion 01 utilizando dos ego vehicles en el mapa 10 de Carla.
Se conducen de forma automática.
La información se imprime en pantalla.
Ejecucion asincrona. El cliente espera un tick del servidor.
Información recogida:
- RGB
- Colisiones
- Invasion de linea
- Obstaculos detectados
- GNSS
- IMU
No probado.

@author Mario Martin <martinperezm@unican.es>, CARLA Simulator Tutorial
@version 1.0.12-25
"""

import carla

import argparse
# import time # Utilizar en caso de añadir sleeps
import logging
import random
import sys

NUM_EGO_VEHICLES = 2
SENSOR_TICK = 5.0

# Blueprints IDs
VEHICLE_MODEL = 'vehicle.tesla.model3'
RGB_SENSOR = 'sensor.camera.rgb'
COLLISION_SENSOR = 'sensor.other.collision'
LANE_SENSOR = 'sensor.other.lane_invasion'
OBSTACLE_SENSOR = 'sensor.other.obstacle'
GNSS_SENSOR = 'sensor.other.gnss'
IMU_SENSOR = 'sensor.other.imu'

def spawn_vehicle_with_attached_sensors(world, ego_bp_id, role_name, spawn_point, sensor_configuration):
    """
    Publica un vehiculo en el servidor de CARLA junto con sus sensores.
    
    :param world: Entorno de CARLA.
    :param ego_bp_id: ID correspondiente al blueprint del vehiculo a generar.
    :param role_name: Nombre identificativo a asignar al vehiculo.
    :param spawn_point_idx: Indice del punto disponible en el que spawnear.
    :param sensor_configuration: Sensores a habilitar.

    Devuelve el vehiculo con una lista de sus sensores.
    """
    sensors = []
    blueprint_library = world.get_blueprint_library()

    # Establecer blueprint del vehiculo
    vehicle_bp = blueprint_library.find(ego_bp_id)
    vehicle_bp.set_attribute('role_name', role_name)
    
    # Color aleatorio (si lo soporta el BP)
    try:
        if 'color' in vehicle_bp.get_attribute('color').recommended_values:
            vehicle_color = random.choice(vehicle_bp.get_attribute('color').recommended_values)
            vehicle_bp.set_attribute('color', vehicle_color)
    except AttributeError:
        pass

    # Spawnear vehiculo
    vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)

    if vehicle is None:
        logging.warning('Error al crear el vehiculo : ' + role_name)
        return None, []
    
    print('\n' + role_name + ' creado.')

    ############
    # SENSORES
    ############

    # Camara RGB
    if sensor_configuration.get('rgb', False):
        cam_bp = blueprint_library.find(RGB_SENSOR)

        # Atributos de camara
        cam_bp.set_attribute('image_size_x', str(1280))
        cam_bp.set_attribute('image_size_y', str(720))
        cam_bp.set_attribute('fov', str(105))

        # Posicion de la camara y rotacion
        cam_location = carla.Location(2, 0, 1)
        cam_rotation = carla.Rotation(0, 180, 0)
        cam_transform = carla.Transform(cam_location, cam_rotation)

        cam = world.spawn_actor(cam_bp, cam_transform, attach_to = vehicle,\
                                    attachment_type = carla.AttachmentType.Rigid)
        
        # Listener: Guardar imagen incluyendo el nombre del vehiculo y el frame
        cam.listen(lambda image: image.save_to_disk('../recorder/sim_01_dataset/%s/rgb/%.6d.jpg' % (role_name, image.frame)))
        sensors.append(cam)

    # Detector de colisiones
    if sensor_configuration.get("col", False):
        col_bp = blueprint_library.find(COLLISION_SENSOR)

        col = world.spawn_actor(col_bp, carla.Transform(), attach_to = vehicle,\
                                    attachment_type = carla.AttachmentType.Rigid)
        
        # Listener: Imprimir la colision
        def col_callback(colli):
            print(role_name + ' - Collision detected:\n' + str(colli) + '\n')
        col.listen(lambda colli: col_callback(colli))
        sensors.append(col)

    # Invasion de linea
    if sensor_configuration.get("lane", False):
        lane_bp = blueprint_library.find(LANE_SENSOR)

        lane = world.spawn_actor(lane_bp, carla.Transform(), attach_to = vehicle,\
                                     attachment_type = carla.AttachmentType.Rigid)
        
        # Listener: Imprimir la invasion de linea
        def lane_callback(lane):
            print(role_name + ' - Lane invasion detected:\n' + str(lane) + '\n')
        lane.listen(lambda lane: lane_callback(lane))
        sensors.append(lane)

    # Obstaculo
    if sensor_configuration.get('obstacle', False):
        obs_bp = blueprint_library.find(OBSTACLE_SENSOR)
        obs_bp.set_attribute('only_dinamics', str(True))

        obs = world.spawn_actor(obs_bp, carla.Transform(), attach_to = vehicle,\
                                    attachment_type = carla.AttachmentType.Rigid)
        
        # Listener: Imprimir la deteccion de obstaculo
        def obs_callback(obs):
            print(role_name + ' - Obstacle detected:\n' + str(obs) + '\n')
        obs.listen(lambda obs: obs_callback(obs))
        sensors.append(obs)

    # GNSS
    if sensor_configuration.get('gnss', False):
        gnss_bp = blueprint_library.find(GNSS_SENSOR)
        gnss_bp.set_attribute('sensor_tick', str(SENSOR_TICK))

        gnss = world.spawn_actor(gnss_bp, carla.Transform(), attach_to = vehicle,\
                                    attachment_type = carla.AttachmentType.Rigid)
        
        # Listener: Imprimir medidas GNSS
        def gnss_callback(gnss):
            print(role_name + ' - GNSS measure: ' + str(gnss) + '\n')
        gnss.listen(lambda gnss: gnss_callback(gnss))
        sensors.append(gnss)
        
    # IMU
    if sensor_configuration.get('imu', False):
        imu_bp = blueprint_library.find(IMU_SENSOR)
        imu_bp.set_attribute('sensor_tick', str(SENSOR_TICK))

        imu = world.spawn_actor(imu_bp, carla.Transform(), attach_to = vehicle,\
                                    attachment_type = carla.AttachmentType.Rigid)
        
        # Listener: Imprimir medidas IMU
        def imu_callback(imu):
            print(role_name + ' - IMU measure:\n' + str(imu) + '\n')
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

    vehicles = []
    ego_vehicle = None

    try:
    
        world = client.get_world()
        
        client.start_recorder('../recorder/recording01.log')

        # Configuracion de sensores
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

        # Blueprint-ID, ROLE_NAME, SPAWN_POINT_INDEX, SENSORES
        vehicle_configs = [
            ('vehicle.tesla.model3', 'ego_1', 0, config_ego_1),
            ('vehicle.audi.a2', 'ego_2', 1, config_ego_2)
        ]

        # Obtencion y mezcla de puntos de spawn
        spawn_points = world.get_map().get_spawn_points()
        random.shuffle(spawn_points)

        # Crear EGO_VEHICLES
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

        # Habilitar piloto automatico
        for vehicle in vehicles:
            vehicle.set_autopilot(True)
        
        while True:
            world.wait_for_tick()
    
    finally:
        print('\nDeteniendo grabacion...')
        client.stop_recorder()

        # Limpieza de vehiculos del simulador
        if vehicles:
            client.apply_batch([carla.command.DestroyActor(x) for x in vehicles])
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
        