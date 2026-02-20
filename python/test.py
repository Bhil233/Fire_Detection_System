from python.upload_image import upload_image, upload_images, FireUploadClient


result = upload_image("fire.jpg")

fire_detected = result["fire_detected"]

if fire_detected:
    print("Fire Detected")
else:
    print("No Fire Detected")