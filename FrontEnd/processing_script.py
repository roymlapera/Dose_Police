def process_txt(file_path):
    result = {}
    try:
        # with open(file_path, 'r') as file:
        #     for line in file:
        #         if ',' in line:
        #             key, value = line.strip().split(',')
        #             result[key] = value
        #         else:
        #             print(f"Skipping invalid line: {line.strip()}")
        result = {'id':'123456', 
                  'patient_name':'Lapera, Roy', 
                  'plan_name':'VMDmBOOST', 
                  'date_time':'2023-12-11-Mon  15:12:30', 
                  'file_path': 'el_file_path_en_cuestion',
                  'constraint_protocol': 'nombre_del_protocolo',
                  'dose_results': {'key1': 10, 
                                    'key2': 10, 
                                    'key3': 10,
                                    'key4': 10, 
                                    'key5': 10, 
                                    'key6': 10,
                                    'key7': 10, 
                                    'key8': 10, 
                                    'key9': 10}
                  } 
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        result = {}
    except Exception as e:
        print(f"An error occurred while processing the file: {e}")
        result = {}
    
    if not result:
        result = {}  # Default result if file is empty or not found
    
    return result

# Example function to get image based on key value
def get_image_for_key(key):
    # Replace this logic with your actual logic for selecting images
    if int(key[-1])%3 == 1:
        return 'checkmark.jpg'
    if int(key[-1])%3 == 2:
        return 'crossmark.jpg'
    else:
        return 'warnmark.jpg'