import sys
import math
import casanova
from PIL import Image
from collections import defaultdict
from datetime import datetime


def weekly_image_count(source_file):

    weeks = defaultdict(int)
    with casanova.reader(source_file) as reader:
        for row in reader:
            formatted_date = row[reader.headers.formatted_date]
            date = datetime.strptime(formatted_date, "%Y-%m-%d")
            weeks[date.isocalendar()[1]] += 1

    return weeks


def stats_on_images_size(source_file, factor, weeks, fixed_width, fixed_height):
    images = defaultdict(list)

    quarter_fixed_width = fixed_width//4

    with casanova.reader(source_file) as reader:
        for row in reader:
            formatted_date = row[reader.headers.formatted_date]
            image_part = row[reader.headers.image_slice]

            date = datetime.strptime(formatted_date, "%Y-%m-%d")
            if date < datetime.strptime("2020-12-31", "%Y-%m-%d") and image_part in ["left", "right"]:

                path = row[reader.headers.absolute_path]
                img = Image.open(path)
                width, height = img.size

                # crop width
                if width < fixed_width:
                    continue

                if image_part == "left":
                    left = width//4 - quarter_fixed_width
                    right =  width//4 + quarter_fixed_width

                else:
                    left = (width//4)*3 - quarter_fixed_width
                    right = (width//4)*3 + quarter_fixed_width

                # crop height
                if height < fixed_height:
                    upper = 0
                    lower = height

                else:
                    upper = height//2 - fixed_height//2
                    lower = height//2 + fixed_height//2

                date = datetime.strptime(formatted_date, "%Y-%m-%d")
                week = date.isocalendar()[1]
                nb_images = math.ceil(weeks[week]/factor)

                if len(images[week]) <= nb_images:
                    images[week].append({
                        "path": path,
                        "crop": (left, upper, right, lower),
                        "x": right - left,
                        "y": lower - upper,
                        "nb_images": nb_images
                    })
    return images


def reduced_timeline(factor):
    source_file = "dame_a_lhermine_slice_images.csv"
    inter_image_space = 100
    fixed_width = 1024
    fixed_height = 1000

    weeks = weekly_image_count(source_file)
    images = stats_on_images_size(source_file, factor, weeks, fixed_width, fixed_height)

    total_width = len(images) * (fixed_width//2 + inter_image_space) - inter_image_space
    total_height = max(sum(im["y"] for im in week) for week in images.values())

    new_im = Image.new('RGB', (int(total_width), int(total_height)),)

    x_offset = 0

    for week in images.values():
        y_offset = total_height
        for im in week:
            image = Image.open(im["path"])
            cropped_img = image.crop(im["crop"])
            new_im.paste(cropped_img, (x_offset,y_offset - cropped_img.size[1]))
            y_offset -= cropped_img.size[1]
        x_offset += fixed_width//2 + inter_image_space

    new_im.save('images_dame_a_lhermine_divided_by_{}.jpg'.format(factor), optimize=True, quality=1)


if __name__=="__main__":
    reduced_timeline(int(sys.argv[1]))