# AUTOGENERATED! DO NOT EDIT! File to edit: s3_scrape.ipynb (unless otherwise specified).

__all__ = ['copy_jpgs', 'build_volume_records', 'scrape_bucket', 'ssda_volume_xml_to_dict']

# Cell

import boto3
import pandas as pd
import os
from PIL import Image
import json

# Cell

def copy_jpgs(json_path, source_bucket, target_bucket):
    s3_client = boto3.client('s3')

    images = 0

    with open(json_path, encoding="utf-8") as jsonfile:
        data = json.load(jsonfile)

    for volume in data["volumes"]:
        for image in volume["images"]:
            #copy_source = {"Bucket": source_bucket, "Key": volume["s3_path"] + "/JPG/" + str(image["file_name"]) + ".JPG"}
            s3_client.download_file(source_bucket, volume["s3_path"] + "/JPG/" + str(image["file_name"]) + ".JPG", "temp.jpg")
            image_number = str(image["file_name"] - 1000)
            padded_number = '0' * (4 - len(image_number)) + image_number
            #s3_client.copy(copy_source, target_bucket, str(volume["identifier"]) + '-' + padded_number + ".jpg", ExtraArgs={'ContentType': "image/jpeg", 'Metadata': {"x-amz-meta-width": str(image["width"]), "x-amz-meta-height": str(image["height"])}})
            s3_client.upload_file("temp.jpg", target_bucket, str(volume["identifier"]) + '-' + padded_number + ".jpg", ExtraArgs={'ContentType': "image/jpeg", 'Metadata': {"width": str(image["width"]), "height": str(image["height"])}})
            images += 1

    os.remove("temp.jpg")

    return str(images) + " images copied from " + source_bucket + " to " + target_bucket

# Cell

def build_volume_records(json_path, target_bucket):
    s3_resource = boto3.resource('s3')
    s3_client = boto3.client('s3')
    #bucket = s3_resource.Bucket(target_bucket)

    volumes = 0

    with open(json_path, encoding="utf-8") as jsonfile:
        data = json.load(jsonfile)

    for volume in data["volumes"]:
        with open("temp.json", 'w', encoding="utf-8") as outfile:
            json.dump(volume, outfile)
        s3_client.upload_file("temp.json", target_bucket, str(volume["identifier"]) + ".json", ExtraArgs={'ContentType': "application/json"})
        volumes += 1

    return "Metadata for " + str(volumes) + " volumes uploaded to S3."

# Cell

def scrape_bucket(bucket_name, prefix=None):
    s3_resource = boto3.resource('s3')
    s3_client = boto3.client('s3')
    bucket = s3_resource.Bucket(bucket_name)

    volume_ids = []
    titles = []
    volume_roots = []
    image_counts = []
    has_jpg = []
    has_tif = []
    has_other = []
    other = []
    has_pdf = []
    has_metadata = []
    volume_metadata = []

    folders = ["jpg", "tif", "metadata"]

    for obj in bucket.objects.filter(Prefix = prefix):
        if (len(obj.key.split('/')) >= 4) and (obj.key.split('/')[3].isdigit()) and (obj.key.split('/')[3] != '') and (obj.key.split('/')[3] not in volume_ids):
            volume_ids.append(obj.key.split('/')[3])
            volume_root = obj.key[:obj.key.find('/', obj.key.find(obj.key.split('/')[3]))]
            volume_roots.append(volume_root)
            has_metadata.append(False)
            has_pdf.append(False)
            has_jpg.append(False)
            has_tif.append(False)
            has_other.append(False)
            other.append(None)
            for volume_obj in bucket.objects.filter(Prefix = volume_root):
                if "DC.xml" in volume_obj.key:
                    has_metadata[-1] = True
                    s3_client.download_file(bucket.name, volume_obj.key, "temp.xml")
                    vol_dict = ssda_volume_xml_to_dict("temp.xml", volume_root)
                    volume_metadata.append(vol_dict)
                    if "title" in vol_dict:
                        titles.append(vol_dict["title"])
                    else:
                        titles.append("no title")
                    os.remove("temp.xml")
                elif "pdf" in volume_obj.key.lower():
                    has_pdf[-1] = True
                elif (has_jpg[-1] == False) and (volume_obj.key.lower().split('/')[4] == "jpg"):
                    has_jpg[-1] = True
                elif (has_tif[-1] == False) and (volume_obj.key.lower().split('/')[4] == "tif"):
                    has_tif[-1] = True
                elif (len(volume_obj.key.split('/')) > 5) and (volume_obj.key.lower().split('/')[4] not in folders) and ((other[-1] == None) or (volume_obj.key.lower().split('/')[4] not in other[-1])):
                    has_other[-1] = True
                    if other[-1] == None:
                        other[-1] = volume_obj.key.lower().split('/')[4]
                    else:
                        other[-1] = other[-1] + '|' + volume_obj.key.lower().split('/')[4]

            image_metadata = []
            prod_imgs = None
            if has_jpg[-1]:
                prod_imgs = "jpg"
            elif has_tif[-1]:
                prod_imgs = "tif"

            if prod_imgs == None:
                volume_metadata[-1]["images"] = []
                image_counts.append(0)
            else:
                bad_images = 0
                for image_obj in bucket.objects.filter(Prefix = volume_root + '/' + prod_imgs.upper()):
                    if ('.' + prod_imgs) in image_obj.key.lower():
                        file_name = image_obj.key[image_obj.key.rfind('/') + 1:image_obj.key.rfind('.')]
                        if not file_name.isdigit():
                            print("found bad image file name at " + image_obj.key)
                            bad_images += 1
                            continue
                        extension = image_obj.key[image_obj.key.rfind('.') + 1:]
                        temp_path = file_name + '.' + extension
                        s3_client.download_file(bucket.name, image_obj.key, temp_path)
                        im = Image.open(temp_path)
                        width, height = im.size
                        im.close()
                        os.remove(temp_path)
                        image = {"file_name": int(file_name), "extension": extension, "height": height, "width": width}
                        image_metadata.append(image)
                volume_metadata[-1]["images"] = image_metadata
                image_counts.append(len(image_metadata) + bad_images)

            print("Completed " + titles[-1])
        elif (len(obj.key.split('/')) >= 5) and (not obj.key.split('/')[3].isdigit()) and (obj.key.split('/')[4] != '') and (obj.key.split('/')[4] not in volume_ids):
            volume_ids.append(obj.key.split('/')[4])
            volume_root = obj.key[:obj.key.find('/', obj.key.find(obj.key.split('/')[4]))]
            volume_roots.append(volume_root)
            has_metadata.append(False)
            has_pdf.append(False)
            has_jpg.append(False)
            has_tif.append(False)
            has_other.append(False)
            other.append(None)
            for volume_obj in bucket.objects.filter(Prefix = volume_root):
                if "DC.xml" in volume_obj.key:
                    has_metadata[-1] = True
                    s3_client.download_file(bucket.name, volume_obj.key, "temp.xml")
                    vol_dict = ssda_volume_xml_to_dict("temp.xml", volume_root)
                    volume_metadata.append(vol_dict)
                    if ("title" in vol_dict) and (vol_dict["title"] != None):
                        titles.append(vol_dict["title"])
                    else:
                        titles.append("no title")
                    os.remove("temp.xml")
                elif "pdf" in volume_obj.key.lower():
                    has_pdf[-1] = True
                elif (has_jpg[-1] == False) and (volume_obj.key.lower().split('/')[5] == "jpg"):
                    has_jpg[-1] = True
                elif (has_tif[-1] == False) and (volume_obj.key.lower().split('/')[5] == "tif"):
                    has_tif[-1] = True
                elif (len(volume_obj.key.split('/')) > 6) and (volume_obj.key.lower().split('/')[5] not in folders) and ((other[-1] == None) or (volume_obj.key.lower().split('/')[5] not in other[-1])):
                    has_other[-1] = True
                    if other[-1] == None:
                        other[-1] = volume_obj.key.lower().split('/')[5]
                    else:
                        other[-1] = other[-1] + '|' + volume_obj.key.lower().split('/')[5]

            if has_metadata[-1] == False:
                titles.append("no title")
                print("Failed to find metadata for " + volume_root)

            image_metadata = []
            prod_imgs = None
            if has_jpg[-1]:
                prod_imgs = "jpg"
            elif has_tif[-1]:
                prod_imgs = "tif"

            if prod_imgs == None:
                volume_metadata[-1]["images"] = []
                image_counts.append(0)
            else:
                bad_images = 0
                for image_obj in bucket.objects.filter(Prefix = volume_root + '/' + prod_imgs.upper()):
                    if ('.' + prod_imgs) in image_obj.key.lower():
                        file_name = image_obj.key[image_obj.key.rfind('/') + 1:image_obj.key.rfind('.')]
                        if not file_name.isdigit():
                            print("found incorrect image file name at " + image_obj.key)
                            bad_images += 1
                            continue
                        extension = image_obj.key[image_obj.key.rfind('.') + 1:]
                        temp_path = file_name + '.' + extension
                        s3_client.download_file(bucket.name, image_obj.key, temp_path)
                        try:
                            im = Image.open(temp_path)
                            width, height = im.size
                            im.close()
                            image = {"file_name": int(file_name), "extension": extension, "height": height, "width": width}
                            image_metadata.append(image)
                        except:
                            print("found bad image file at " + image_obj.key)
                            bad_images += 1
                        os.remove(temp_path)
                volume_metadata[-1]["images"] = image_metadata
                image_counts.append(len(image_metadata) + bad_images)

            try:
                print("Completed " + titles[-1])
            except:
                print("Completed")
                print(titles[-1])

    volumes_dict = {"id": volume_ids, "title": titles, "images": image_counts, "s3 root": volume_roots, "metadata": has_metadata, "has pdf": has_pdf, "has jpg": has_jpg, "has tif": has_tif, "has other": has_other, "other": other}
    volumes_df = pd.DataFrame.from_dict(volumes_dict)

    return volumes_df, volume_metadata

# Cell

def ssda_volume_xml_to_dict(volume_xml, s3_path):
    import xml.etree.ElementTree as ET
    tree = ET.parse(volume_xml)
    root = tree.getroot()
    volume_dict = {}
    volume_dict["s3_path"] = s3_path
    for item in root:
        if "{http://purl.org/dc/elements/1.1/}" in item.tag:
            item.tag = item.tag[item.tag.find('}') + 1:]
        if item.text == None:
            if item.tag not in volume_dict:
                volume_dict[item.tag] = None
            continue
        if item.text[0] == ' ':
            item.text = item.text[1:]
        if item.tag == "subject":
            if "subject" in volume_dict:
                volume_dict["subject"].append(item.text.split("--"))
            else:
                volume_dict["subject"] = item.text.split("--")
        elif item.tag == "title":
            volume_dict["title"] = item.text
        elif item.tag == "contributor":
            if (item.text.find('(') != -1) and (item.text.find(')') != -1):
                name = item.text[:item.text.find('(')]
                role = item.text[item.text.find('(') + 1:item.text.find(')')]
            else:
                continue
            if "contributor" in volume_dict:
                volume_dict["contributor"].append({"name": name, "role": role})
            else:
                volume_dict["contributor"] = [{"name": name, "role": role}]
        elif item.tag == "identifier":
            volume_dict["identifier"] = item.text[item.text.find(':') + 1:]
        elif item.tag == "coverage":
            if ('.' in item.text) and (',' in item.text) and ("Archives" not in item.text):
                if "coverage" in volume_dict:
                    volume_dict["coverage"]["coords"] = item.text
                else:
                    volume_dict["coverage"] = {"coords": item.text}
            elif "--" in item.text:
                places = item.text.split("--")
                if len(places) == 4:
                    if "coverage" in volume_dict:
                        volume_dict["coverage"]["country"] = places[1]
                        volume_dict["coverage"]["state"] = places[2]
                        volume_dict["coverage"]["city"] = places[3]
                    else:
                        volume_dict["coverage"] = {"country": places[1], "state": places[2], "city": places[3]}
        elif item.tag == "source":
            if "coverage" in volume_dict:
                volume_dict["coverage"]["institution"] = item.text
            else:
                volume_dict["coverage"] = {"institution": item.text}
        elif ((item.tag == "type") and (item.text == "Text")) or (item.tag == "rights"):
            continue
        elif (item.tag == "creator") and (';' in item.text):
            creators = item.text.split(';')
            for creator in creators:
                if (len(creator) > 1) and (creator[0] == ' '):
                    creator = creator[1:]
                if "creator" in volume_dict:
                    volume_dict["creator"].append(creator)
                else:
                    volume_dict["creator"] = [creator]
        elif (item.tag == "language") and (';' in item.text):
            languages = item.text.split(';')
            for language in languages:
                if (len(language) > 1) and (language[0] == ' '):
                    language = language[1:]
                if "language" in volume_dict:
                    volume_dict["language"].append(language)
                else:
                    volume_dict["language"] = [language]
        else:
            if item.tag in volume_dict:
                volume_dict[item.tag].append(item.text)
            else:
                volume_dict[item.tag] = [item.text]

    if "coverage" not in volume_dict:
        volume_dict["coverage"] = {}
        volume_dict["coverage"]["country"] = volume_dict["s3_path"].split('/')[0].replace('_', ' ')
        volume_dict["coverage"]["state"] = volume_dict["s3_path"].split('/')[1].replace('_', ' ')
        volume_dict["coverage"]["city"] = volume_dict["s3_path"].split('/')[2].replace('_', ' ')
        volume_dict["coverage"]["institution"] = volume_dict["s3_path"].split('/')[3].replace('_', ' ')
    elif "institution" not in volume_dict["coverage"]:
        volume_dict["coverage"]["institution"] = volume_dict["s3_path"].split('/')[3].replace('_', ' ')

    return volume_dict