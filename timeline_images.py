import sys
import math
import random
import casanova
import imagehash
import numpy as np
from tqdm import tqdm
from PIL import Image
from datetime import datetime


def iterate_over_weeks():
    start = datetime.strptime("2020-03-01", "%Y-%m-%d")
    end = datetime.strptime("2020-12-31", "%Y-%m-%d")
    for i in range((end - start).days//7 + 1):
        yield i + 1


def weekly_image_count(source_file):
    print("Compute weekly image count")
    weeks = {w: 0 for w in iterate_over_weeks()}
    with casanova.reader(source_file) as reader:
        for row in tqdm(reader, total=casanova.count(source_file)):
            utc_time = row[reader.headers.utc_time]
            if "2020" in utc_time:
                date = datetime.strptime(utc_time, "%Y-%m-%dT%H:%M:%S")
                week = date.isocalendar()[1]
                if week in weeks:
                    weeks[week] += 1

    return weeks


def is_duplicate(image, hashes):
    image = image.convert("L").resize((8, 8), Image.LANCZOS)
    data = image.getdata()
    quantiles = np.arange(100)
    quantiles_values = np.percentile(data, quantiles)
    zdata = (np.interp(data, quantiles_values, quantiles) / 100 * 255).astype(np.uint8)
    image.putdata(zdata)
    hash = imagehash.dhash(image)
    if hash in hashes:
        return True, hashes
    hashes.add(hash)
    return False, hashes


def stats_on_images_size(source_file, factor, weeks, fixed_width, resize_width):
    images = {w: [] for w in weeks}

    quarter_fixed_width = fixed_width//4
    print("Compute stats on image size")
    with casanova.reverse_reader(source_file) as reader:
        hashes = set()

        image_slices_are_given = "image_slice" in reader.headers
        absolute_paths_are_given = "absolute_path" in reader.headers

        for row in tqdm(reader, total=casanova.count(source_file)):
            utc_time = row[reader.headers.utc_time]

            if "2020" not in utc_time:
                continue

            if image_slices_are_given:
                image_part = row[reader.headers.image_slice]
                if image_part not in ["left", "right"]:
                    continue
            else:
                image_part = random.choice(["left", "right"])

            if absolute_paths_are_given:
                path = row[reader.headers.absolute_path]
            else:
                path = row[reader.headers.filename]

            if not (path.endswith("jpg") or path.endswith("png")):
                continue

            date = datetime.strptime(utc_time, "%Y-%m-%dT%H:%M:%S")
            week = date.isocalendar()[1]

            if week not in weeks:
                continue

            nb_images = math.ceil(weeks[week]/factor)
            if len(images[week]) < nb_images:

                img = Image.open(path)

                duplicate, hashes = is_duplicate(img, hashes)
                if duplicate:
                    continue

                width, height = img.size

                if image_part == "left":
                    left = width//4 - quarter_fixed_width
                    right =  width//4 + quarter_fixed_width

                else:
                    left = (width//4)*3 - quarter_fixed_width
                    right = (width//4)*3 + quarter_fixed_width

                resized_height = int(resize_width*height/(fixed_width//2))

                images[week].append({
                    "path": path,
                    "crop": (left, 0, right, height),
                    "x": right - left,
                    "y": resized_height,
                    "nb_images": nb_images
                })
    return images


def reduced_timeline(source_file, outfile, factor):
    inter_image_space = 100
    fixed_width = 900
    resize_width = 200

    weeks = weekly_image_count(source_file)
    images = stats_on_images_size(source_file, factor, weeks, fixed_width, resize_width)

    total_width = len(images) * (resize_width + inter_image_space) - inter_image_space
    total_height = max(sum(im["y"] for im in week) for week in images.values())

    new_im = Image.new('RGB', (int(total_width), int(total_height)),)

    x_offset = 0

    print("Write chart")
    for week in tqdm(images.values(), total=len(images)):
        y_offset = total_height
        for im in week:
            image = Image.open(im["path"])
            cropped_img = image.crop(im["crop"])
            resized_img = cropped_img.resize((resize_width, im["y"]))
            new_im.paste(resized_img, (x_offset,y_offset - resized_img.size[1]))
            y_offset -= resized_img.size[1]
        x_offset += resize_width + inter_image_space

    new_im.save(outfile.replace(".jpg", "_divided_by_{}.jpg".format(factor)), optimize=True, quality=20)


if __name__=="__main__":
    reduced_timeline(sys.argv[1], sys.argv[2], int(sys.argv[3]))