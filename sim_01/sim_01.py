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

# TICKS
SENSOR_TICK = 0.5
WORLD_TICK = 0.05
FRAME_TOLERANCE = 2

# BLUEPRINTS
RGB_SENSOR = 'sensor.camera.rgb'
COLLISION_SENSOR = 'sensor.other.collision'
LANE_SENSOR = 'sensor.other.lane_invasion'
OBSTACLE_SENSOR = 'sensor.other.obstacle'
GNSS_SENSOR = 'sensor.other.gnss'
IMU_SENSOR = 'sensor.other.imu'

# DIRECTORIOS
OUTPUT_DIR = "../recorder/sim_01_datamodel"
IMG_SUBDIR = "rgb_images"

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
    sensors = ['rgb', 'collision', 'lane', 'obstacle', 'gnss', 'imu']

    for s in sensors:
        response = input(f"¿Activar {s.upper()}? > ").lower()
        config[s] = response in ['s', 'y']
    return config

def create_camera(world, bp_lib, size_x, size_y, fov, location, rotation, vehicle):
    """
    Crea una camara RGB y la asigna a un vehiculo determinado.
    Retorna la camara creada.
    
    :param world: Entorno de simulacion.
    :param bp_lib: Libreria de blueprints.
    :param size_x: Tamaño horizontal de la imagen.
    :param size_y: Tamaño vertical de la imagen.
    :param fov: FOV de la imagen.
    :param location: Ubicacion relativa de la camara con respecto al vehiculo.
    :param rotation: Desplazamiento rotacional de la camara.
    :param vehicle: Vehiculo al que fijar la camara.
    """
    cam_bp = bp_lib.find(RGB_SENSOR)

    # Establecer atributos de imagen
    cam_bp.set_attribute('image_size_x', str(size_x))
    cam_bp.set_attribute('image_size_y', str(size_y))
    cam_bp.set_attribute('fov', str(fov))
    cam_bp.set_attribute('sensor_tick', str(SENSOR_TICK))
    
    # Establecer atributos de ubicacion y giro
    cam_transform = carla.Transform(location, rotation)

    # Crear camara
    cam = world.spawn_actor(cam_bp, cam_transform, attach_to = vehicle, \
                            attachment_type = carla.AttachmentType.Rigid)
    
    return cam

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

    ############
    # SENSORES #
    ############

    def push_data(sensor_type, data_payload):
        """
        Recoger los datos para su persistencia.
        
        :param sensor_type: Tipo de datos del sensor a guardar.
        :param data_payload: Datos a guardar.
        """
        timestamp = datetime.now().isoformat()
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
            filename = f"{image.frame:06d}.jpg"
            vehicle_dir = os.path.join(OUTPUT_DIR, role_name)
            img_dir_abs = os.path.join(vehicle_dir, IMG_SUBDIR)
            abs_path = os.path.join(img_dir_abs, filename)

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
        obs_bp.set_attribute('only_dynamics', str(True))

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
        def imu_callback(event):
            push_data("imu", {
                "frame": event.frame,
                "accelerometer": {"x": event.accelerometer.x, "y": event.accelerometer.y, "z": event.accelerometer.z},
                "gyroscope": {"x": event.gyroscope.x, "y": event.gyroscope.y, "z": event.gyroscope.z},
                "compass": event.compass
            })
        imu.listen(lambda event: imu_callback(event))
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

#   # Cola de recepcion de datos de los sensores
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
            vehicle_path = os.path.join(OUTPUT_DIR, role_name, IMG_SUBDIR)
            if not os.path.exists(vehicle_path):
                os.makedirs(vehicle_path)

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
            client.apply_batch([carla.command.DestroyActor(v) for v in vehicles])
            print('\nVehiculos y sensores eliminados.')
        else:
            print('\nNo hay vehiculos por eliminar.')

if __name__ == '__main__':
    main()