import paho.mqtt.client as mqtt
import json
import os
import time
import requests
import collections
from datetime import datetime, timedelta

# ฟังก์ชันสำหรับส่งข้อความแจ้งเตือนไปที่ LINE
def send_line_notification(message, line_token):
    url = "https://notify-api.line.me/api/notify"
    headers = {
        "Authorization": f"Bearer {line_token}"
    }
    data = {
        "message": message
    }
    response = requests.post(url, headers=headers, data=data)
    if response.status_code != 200:
        print(f"Error sending notification: {response.status_code} {response.text}")

# กำหนดการตั้งค่า MQTT
thingsboard_host = 'demo.thingsboard.io'
access_token = 'xQtlcR0LAgwuvN6cL3tG'
line_token = 'noNtFQH2K31zam2rlex8RpBnnEIO5LIPUj8Vb4zRcZa'

# ฟังก์ชันเพื่อค้นหาข้อมูลล่าสุด
def find_latest_data(lines):
    latest_time = None
    latest_data = {}
    for line in lines:
        if line.startswith("Time"):
            time_str = line.split("Time")[1].strip()
            if latest_time is None or time_str > latest_time:
                latest_time = time_str
                latest_data["time"] = time_str
        elif line.startswith("Receive as String") and "time" in latest_data:
            latest_data["receive_as_string"] = line.split(":", 1)[1].strip()
        elif line.startswith("SNR") and "time" in latest_data:
            try:
                snr_value = float(line.split(":")[1].strip().replace('\x00', ''))
                latest_data["SNR"] = snr_value
            except ValueError:
                print(f"Error converting SNR value: {line}")
                latest_data["SNR"] = None
        elif line.startswith("RSSI") and "time" in latest_data:
            try:
                rssi_value = int(line.split(":")[1].strip())
                latest_data["RSSI"] = rssi_value
            except ValueError:
                print(f"Error converting RSSI value: {line}")
                latest_data["RSSI"] = None
    return latest_data

# ฟังก์ชันตรวจสอบข้อมูลที่ซ้ำกัน
def check_repeated_entries(latest_data, previous_data):
    if latest_data == previous_data:
        return False
    return True

last_notification_time = datetime.now() - timedelta(minutes=1)
previous_data = None
status = False
_count = 0

while True:
    try:
        client = mqtt.Client()
        client.username_pw_set(access_token)
        client.connect(thingsboard_host, 1883, 60)
        today = datetime.today().strftime('%Y-%m-%d')

        file_path = f'/home/LoRaGW3/Documents/LoRaRice_Spare/log/logfile_Receive_LoRaRice_{today}.txt'

        with open(file_path, 'r') as file:
            lines = file.readlines()

        latest_data = find_latest_data(lines)

        # ตรวจสอบข้อมูลซ้ำ
        if check_repeated_entries(latest_data, previous_data):
            status = True
            previous_data = latest_data  # อัปเดตข้อมูลก่อนหน้า
        else:
            status = False

        values = latest_data.get("receive_as_string", "").split(',')
        if len(values) >= 7:
            distance = values[0]
            temperature = values[1]
            humidity = values[2]
            voltage = values[3]
            humSoil = values[4]
            tempSoil = values[5]
            ec = values[6]
            snr = latest_data.get("SNR", None)
            rssi = latest_data.get("RSSI", None)
            time_log = latest_data.get("time", None)

            try:
                distance_int = int(float(distance))
                distance_calculated = distance_int
            except ValueError:
                print("Error converting distance to integer.")
                distance_calculated = None

            current_time = datetime.now()
            formatted_time = current_time.strftime("%H:%M:%S")

            res = os.popen('vcgencmd measure_temp').readline()
            temp_pi = float(res.replace("temp=","").replace("'C\n",""))

            try:
                distance_int = int(float(distance))
                distance_calculated = distance_int
            except ValueError:
                print("Error converting distance to integer.")
                distance_calculated = None

            try:
                voltage_float = float(voltage)
            except ValueError:
                print("Error converting voltage to float.")
                voltage_float = None

            print(time_log)
            print("Distance:", distance_calculated)
            print("Temperature:", temperature)
            print("Humidity:", humidity)
            print("Voltage:", voltage)
            print("HumSoil:", humSoil)
            print("TempSoil:", tempSoil)
            print("EC:", ec)
            print("SNR:", snr)
            print("RSSI:", rssi)
            print("Pi_temp", temp_pi)
            print("Status:", status)
            print("==============================================")

            payload = {
                "time": latest_data.get("time"),
                "distance": distance_calculated,
                "temperature": temperature,
                "humidity": humidity,
                "voltage": voltage,
                "humSoil": humSoil,
                "tempSoil": tempSoil,
                "EC": ec,
                "SNR": snr,
                "RSSI": rssi,
                "Pi_temp": temp_pi,
                "Status": status
            }

            payload = {k: v for k, v in payload.items() if v is not None}
            client.publish('v1/devices/me/telemetry', json.dumps(payload))

        else:
            print("Error: Not enough data received.")

        current_time = datetime.now()
        if status == False:
            if _count == 0:
                send_line_notification("Status Node is Disconnect", line_token)
                _count += 1
        else :
            _count = 0
            if current_time - last_notification_time >= timedelta(minutes=1):
                send_line_notification(f"ระดับน้ำปัจจุบัน  : {distance_calculated} cm \n อุณหภูมิในดิน : {tempSoil} Celsius \n ความชื้นในดิน : {humSoil} % \n ค่า EC ในดิน : {ec} mS/cm \n อุณหภูมิในโหนด : {temperature} Celsius \n ความชื้นในโหนด : {humidity} % \n แรงดันไฟฟ้า : {voltage} V \n SNR : {snr} dB \n RSSI : {rssi} dBm.", line_token)

                if distance_calculated <= 0:
                    send_line_notification("ระดับน้ำเหลือ 0 cm", line_token)
                elif distance_calculated > 15:
                    send_line_notification("ระดับน้ำมากกว่า 15 cm", line_token)
                if voltage_float and voltage_float < 3.0:
                    send_line_notification("แบตต่ำ", line_token)

                last_notification_time = current_time
            

    except Exception as e:
        node_status = False
        payload = {"Node_Status": node_status}
        payload = {k: v for k, v in payload.items() if v is not None}
        client.publish('v1/devices/me/telemetry', json.dumps(payload))
        print(f"Error: {e}")

    time.sleep(10)
