import os
import sys
import casanova
import base64
from io import BytesIO
from tqdm import tqdm
from PIL import Image
from datetime import datetime
from collections import defaultdict


input_date_fmt = "%Y-%m-%dT%H:%M:%S"
reclusters = {384: 7,
              1554: 33,
              460: 33,
              151: 33,
              2127: 61,
              47: 25,
              130: 36,
              2848: 36,
              38: 3,
              2578: 11,
              593: 53,
              247: 52,
              69: 52,
              94: 52,
              139: 52,
}

zooms = {
    3: {"x": 94, "y": 5, "width": 7, "height": 7} #jf à la perle, carré de 7 images par 7 images
}


def sort_quality(clusters, min_cluster):
    size_quality_buckets = defaultdict(dict)
    date_buckets = defaultdict(int)

    # Sort clusters by size and by quality. Write first big clusters with high quality.
    # Skip clusters with quality < 1.

    for size in [25 * (2**i) for i in range(3, -1, -1)] + [min_cluster]:
        for quality in range(4, 0, -1):
            size_quality_buckets[size][quality] = []

    for cluster_id, cluster in clusters.items():
        size = cluster["count"]
        quality = cluster["quality"]
        for s in size_quality_buckets:
            if size > s:
                for q in size_quality_buckets[s]:
                    if quality > q:
                        cluster["id"] = cluster_id
                        size_quality_buckets[s][q].append(cluster)

                        for _, date in cluster["images"]:
                            date_buckets[date] += 1

                        quality = 0
                        size = 0
                        break

    return size_quality_buckets, date_buckets


def resize_image_to_square(image_path, size):
    image = Image.open(image_path)
    resized_image = image.resize((size, size))
    return resized_image


def stats_on_images(source_file, images_dir, date_fmt, min_cluster):

    clusters = dict()

    with casanova.reader(source_file) as reader:
        utc_time = reader.headers.utc_time
        cluster_id = reader.headers.cluster_id
        quality = reader.headers.quality
        path = lambda row: os.path.join(images_dir, row[reader.headers.path])

        for row in tqdm(reader, total=casanova.count(source_file)):
            date = datetime.strptime(row[utc_time], input_date_fmt).strftime(date_fmt)
            cluster = int(row[cluster_id])

            if cluster in reclusters:
                cluster = reclusters[cluster]

            if cluster not in clusters:
                clusters[cluster] = {"quality": float(row[quality])*100, "count": 0, "images": []}
            clusters[cluster]["count"] += 1
            clusters[cluster]["images"].append((path(row), date))

    for cluster_id in reclusters.values():
        clusters[cluster_id]["quality"] = 4.5

    quality_buckets, date_buckets = sort_quality(clusters, min_cluster)

    return date_buckets, quality_buckets


def write_timeline(source_file, images_dir, out_folder, granularity, size, min_cluster):
    if granularity == "day":
        date_fmt = "%Y-%m-%d"
    elif granularity == "week":
        date_fmt = "%Y-%W"


    date_buckets, image_buckets = stats_on_images(source_file, images_dir, date_fmt, min_cluster)
    date_indices  = list(sorted(date_buckets))

    max_bucket = max(date_buckets.values())
    nb_buckets = len(date_buckets)

    print("Image size will be {} x {} (largeur x hauteur)".format(nb_buckets*size, max_bucket*size))

    y_offsets = {key: max_bucket*size for key in date_indices}

    os.makedirs(out_folder, exist_ok=True)

    #total_image = Image.new('RGBA', (nb_buckets*size, max_bucket*size), color=(255, 255, 255, 0))

    total_file = os.path.join(out_folder, "all_moreThan{}_{}Columns_{}Pixels".format(min_cluster, granularity, size))

    with open(total_file + ".svg", "w") as svgf:
        svgf.write("""<svg xmlns="http://www.w3.org/2000/svg"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  width="{}px" height="{}px"
  style="background-color: black">
""".format(nb_buckets*size, max_bucket*size))

        with tqdm(total=casanova.count(source_file)) as pbar:

            for s in image_buckets:
                for cluster_list in image_buckets[s].values():
                    for cluster in sorted(cluster_list, key=lambda x: x["count"], reverse=True):
                        svgf.write('  <g id="{}">\n'.format(cluster["id"]))

                        for image_path, image_date in cluster["images"]:
                            x_offset = date_indices.index(image_date) * size
                            y_offset = y_offsets[image_date] - size
                            try:
                                thumbnail = resize_image_to_square(image_path, size)

                                buffered = BytesIO()
                                thumbnail.save(buffered, format="PNG")
                                img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
                                svgf.write('    <image x="{}" y="{}" width="{}" height="{}" xlink:href="data:image/png;base64,{}" />\n'.format(
                                    x_offset, y_offset, size, size, img_str)
                                )

                                y_offsets[image_date] = y_offset

                            except FileNotFoundError:
                                pass

                        if cluster["id"] in zooms:
                            zoom = zooms[cluster["id"]]

                            bottom_line = (zoom["x"], max_bucket - zoom["y"], zoom["x"] + zoom["width"], max_bucket - zoom["y"])
                            bottom_line = (i * size for i in bottom_line)
                            svgf.write('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="red" stroke-width="5" />'.format(
                                *bottom_line
                            ))

                            top_line = (
                                zoom["x"],
                                max_bucket - zoom["y"] - zoom["height"],
                                zoom["x"] + zoom["width"],
                                max_bucket - zoom["y"] - zoom["height"]
                            )
                            top_line = (i * size for i in top_line)
                            svgf.write('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="red" stroke-width="5" />'.format(
                                *top_line
                            ))

                            left_line = (zoom["x"], max_bucket - zoom["y"] - zoom["height"], zoom["x"], max_bucket - zoom["y"])
                            left_line = (i * size for i in left_line)
                            svgf.write('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="red" stroke-width="5" />'.format(
                                *left_line
                            ))

                            right_line = (zoom["x"] + zoom["width"],
                                          max_bucket - zoom["y"] - zoom["height"],
                                          zoom["x"] + zoom["width"],
                                          max_bucket - zoom["y"]
                                          )
                            right_line = (i * size for i in right_line)
                            svgf.write('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="red" stroke-width="5" />'.format(
                                *right_line
                            ))

                        svgf.write('  </g>\n')

                        pbar.update(cluster["count"])

        svgf.write('</svg>\n')

    #total_image.save(total_file + ".png", "PNG")



if __name__=="__main__":
    write_timeline(sys.argv[1], sys.argv[2], sys.argv[3], "day", 16, 5)
