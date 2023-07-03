import sys
import math
import casanova
import imagehash
import numpy as np
from PIL import Image
from datetime import datetime


def iterate_over_weeks():
    start = datetime.strptime("2020-01-01", "%Y-%m-%d")
    end = datetime.strptime("2020-12-31", "%Y-%m-%d")
    for i in range((end - start).days//7 + 1):
        yield i + 1


def weekly_image_count(source_file):

    weeks = {w: 0 for w in iterate_over_weeks()}
    with casanova.reader(source_file) as reader:
        for row in reader:
            formatted_date = row[reader.headers.formatted_date]
            date = datetime.strptime(formatted_date, "%Y-%m-%d")
            weeks[date.isocalendar()[1]] += 1

    return weeks


def is_duplicate(image, hashes):
    copy = image.copy()
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

    with casanova.reader(source_file) as reader:
        hashes = set()
        for row in reader:
            formatted_date = row[reader.headers.formatted_date]
            image_part = row[reader.headers.image_slice]

            date = datetime.strptime(formatted_date, "%Y-%m-%d")
            if date < datetime.strptime("2020-12-31", "%Y-%m-%d") and image_part in ["left", "right"]:

                path = row[reader.headers.absolute_path]
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

                date = datetime.strptime(formatted_date, "%Y-%m-%d")
                week = date.isocalendar()[1]
                nb_images = math.ceil(weeks[week]/factor)

                if len(images[week]) <= nb_images:
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

    for week in images.values():
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