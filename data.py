"""Converts a dataset into the format we expect for training.
"""

from keras.applications.resnet50 import preprocess_input
from keras.preprocessing import image

import argparse
import cv2
import h5py
import json
import numpy as np
import sys
import os

class VRDDataset():
    """Parses the VRD dataset into a format used for training.
    """

    def __init__(self, data_path, img_dir, im_metadata_path, num_predicates=70, num_objects=100, im_dim=224):
        """Constructor for the VRD dataset object.

        Args:
            data_path: Annotations in the VRD dataset.
            img_dir: Location of the images.
            im_metadata_path: Location of the file containing image metadata.
            num_predicates: Number of predicate categories.
            num_objects: Number of object categories.
            im_dim: The size of images.
        """
        self.data = json.load(open(data_path))
        self.im_metadata = json.load(open(im_metadata_path))
        self.im_dim = im_dim
        self.col_template = np.arange(self.im_dim).reshape(1, self.im_dim)
        self.row_template = np.arange(self.im_dim).reshape(self.im_dim, 1)
        self.img_dir = img_dir
        self.train_image_ids = []
        self.val_image_ids = []
        self.num_predicates = num_predicates
        self.num_objects = num_objects

    def rescale_bbox_coordinates(self, bbox, height, width):
        """Rescales the bbox coords according to the `im_dim`.

        Args:
            obj: object containing.
            height: original image height.
            width: original image width.
        Returns:
            A tuple containing the rescaled bbox coordinates.
        """
        h_ratio = self.im_dim * 1. / height
        w_ratio = self.im_dim * 1. / width
        y_min, y_max, x_min, x_max = obj['bbox']
        y0 = max(y_min * h_ratio, 0)
        x0 = max(x_min * w_ratio, 0)
        y1 = min(y_max * h_ratio, self.im_dim - 1)
        x1 = min(x_max * w_ratio, self.im_dim - 1)
        return y0, x0, y1, x1

    def get_regions_from_bbox(self, bbox):
        """Converts a bbox into a binary image for gt regions.

        Args:
            bbox: A tuple of (top, left, bottom, right) coordinates of the
              object of interest.

        Returns:
            An image array with 0 or 1 for ground truth regions.
        """
        top, left, bottom, right = bbox
        col_indexes = (1 * (self.col_template > left) *
                       (self.col_template < right)).repeat(self.im_dim, 0)
        row_indexes = (1 * (self.row_template > top) *
                       (self.row_template < bottom)).repeat(self.im_dim, 1)
        return col_indexes * row_indexes

    def get_train_val_splits(self, val_percent, shuffle=True):
        """Splits the dataset into train and val splits.

        Args:
            val_percent: float, proportion of examples that should be in val.

        Returns:
            A tuple containing the image ids in the train and val sets.
        """
        image_ids = list(self.data.keys())
        if shuffle:
            np.random.shuffle(image_ids)
        thresh = int(len(image_ids) * (1. - val_percent))
        self.train_image_ids = image_ids[:thresh]
        self.val_image_ids = image_ids[thresh:]
        return self.train_image_ids, self.val_image_ids

    def build_and_save_dataset(self, save_dir, image_ids=None):
        """Converts the dataset into format we will use for training.

        Converts the dataset into a series of images, relationship labels
        and heatmaps.

        Args:
            save_dir: Location to save the data.
            image_ids: List of image ids.
        """
        (relationships, object2cat, cat2object,
         predicate2cat, cat2predicate) = self.build_dataset(save_dir,
                                                            image_ids=image_ids)
        self.save_dataset(relationships, object2cat, cat2object,
                          predicate2cat, cat2predicate)

    def build_dataset(self, save_dir, image_ids=None):
        """Converts the dataset into a list of relationships and categories.

        Args:
            save_dir: Location to save the data.
            image_ids: List of image ids.

        Returns:
            relationships: A list containing objects that contain:
                - 'image': The numpy image representation.
                - 'subject': The numpy subject location mask.
                - 'object': The numpy object location mask.
                - 'categories': A list of subject, object and predicate indices.
        """
        # TODO
        if not image_ids:
            image_ids = self.data.keys()

    def save_dataset(self, relationships, object2cat, cat2object,
                     predicate2cat, cat2predicate):
        """Converts the dataset into hdf5.

        Args:
            relationships: A list containing objects that contain:
                - 'image': The numpy image representation.
                - 'subject': The numpy subject location mask.
                - 'object': The numpy object location mask.
                - 'categories': A list of subject, object and predicate indices.
            object2cat: A mapping from object names to categories.
            cat2object: A mapping from category index to object name.
            predicate2cat: A mapping from predicate names to categories.
            cat2predicate: A mapping from category index to predicate name.
        """
        # TODO

        total_relationships = len(relationships)
        dataset = h5py.File(filename, 'w')
        images_db = dataset.create_dataset('images',
                                           (len(total_relationships),
                                            self.input_dim, self.input_dim, 3),
                                           dtype='f')
        categories_db = dataset.create_dataset('categories',
                                               (len(total_relationships), 3),
                                               dtype='f')
        subject_db = dataset.create_dataset('subject_location',
                                            (len(total_relationships),
                                             self.input_dim, self.input_dim),
                                            dtype='f')
        object_db = dataset.create_dataset('object_location',
                                           (len(total_relationships),
                                            self.input_dim, self.input_dim),
                                           dtype='f')
        nb_images = len(image_ids)
        for i, image_id in enumerate(image_ids):
            im_data = self.im_metadata[image_id]
            for j, relationship in enumerate(self.data[image_id]):
                rel_id = image_id.split('.')[0] + '-{}'.format(j)
                subject_id = relationship['subject']['category']
                predicate_id = relationship['predicate']
                object_id = relationship['object']['category']
                relationships += [(subject_id, predicate_id, object_id)]
                s_bbox = self.rescale_bbox_coordinates(relationship['subject']['bbox'], im_data['height'], im_data['width'])
                o_bbox= self.rescale_bbox_coordinates(relationship['object']['bbox'], im_data['height'], im_data['width'])
                s_region = self.get_regions_from_bbox(s_bbox)
                o_region = self.get_regions_from_bbox(o_bbox)
            if i % 100 == 0:
                print('{}/{} images processed'.format(i, nb_images))

    def get_image_from_img_id(self, img_id):
        """Reads the image associated with a specific img_id.

        Args:
            img_id: The if of the image to be read.

        Returns:
            The image as a numpy array.
        """
        img_path = os.path.join(self.img_dir, img_id)
        img = image.load_img(img_path, target_size=(224, 224))
        img_array = image.img_to_array(img)

        # Preprocess the image according to the network we are using.
        img_array = np.expand_dims(img_array, axis=0)
        img_array = preprocess_input(img_array)
        return img_array[0]

    def get_images(self, image_ids):
        """Loads all the images in the list of image_ids.

        Args:
            image_ids: A list of image ids.

        Returns:
            images: A list of numpy representations of the images.
        """
        images = np.zeros((len(image_ids), self.im_dim, self.im_dim, 3))
        for i, image_id in enumerate(image_ids):
            images[i] = self.get_image_from_img_id(image_id)
        return images

    def get_images_and_regions(self, image_ids, subject_bboxs, object_bboxs):
        """Grabs the image and subject-object locations.

        Args:
            image_ids: A list of image ids to load.
            subject_bboxes: A list of subject bboxes.
            object_bboxes: A list of object bboxes.

        Returns:
            A tuple containing a numpy representation of all the images,
            a numpy representation of all the subject locations,
            a numpry representation of all the object locations.
        """
        num_images = len(image_ids)
        images = np.zeros((num_images, self.im_dim, self.im_dim, 3))
        s_regions = np.zeros((num_images, self.im_dim * self.im_dim))
        o_regions = np.zeros((num_images, self.im_dim * self.im_dim))
        for i, image_id in enumerate(image_ids):
            s_bbox = subject_bboxes[i]
            o_bbox = object_bboxes[i]
            images[i] = self.get_image_from_img_id(image_id)
            s_regions[i] = self.get_regions_from_bbox(s_bbox)
            o_regions[i] = self.get_regions_from_bbox(o_bbox)
        return images, s_regions, o_regions


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Dataset creation for Visual '
                                     'Relationship model. This scripts saves '
                                     'masks for objects and subjects in '
                                     'directories, as well as numpy arrays '
                                     'for relationships.')
    parser.add_argument('--test', action='store_true',
                        help='When true, the data is not split into training '
                        'and validation sets')
    parser.add_argument('--val-percent', type=float, default=0.1,
                        help='Fraction of images in validation split.')
    parser.add_argument('--save-dir', type=str, default=None,
                        help='where to save the ground truth masks, this '
                        'Location where dataset should be saved.')
    parser.add_argument('--img-dir', type=str, default=None,
                        help='Location where images are stored.')
    parser.add_argument('--annotations', type=str,
                        default='data/VRD/annotations_train.json',
                        help='Json with relationships for each image.')
    parser.add_argument('--image-metadata', type=str,
                        default='data/VRD/image_metadata.json',
                        help='Image metadata json file.')
    parser.add_argument('--seed', type=int, default=1234,
                        help='The random seed used to reproduce results.')
    args = parser.parse_args()

    # Make sure that the required fields are present.
    if args.save_dir is None:
        print '--save-dir not specified. Exiting!'
        sys.exit(0)
    if args.img_dir is None:
        print '--img-dir not specified. Exiting!'
        sys.exit(0)

    # set the random seed.
    np.random.seed(args.seed)

    dataset = VRDDataset(args.annotations, args.img_dir,
                             args.image_metadata)
    if args.test:
        # Build the test dataset.
        test_dir = os.path.join(args.save_dir, 'test')
        os.mkdir(test_dir)
        dataset.build_and_save_dataset(test_dir)
    else:
        # Split the images into train and val datasets.
        train_split, val_split = dataset.get_train_val_splits(
            args.val_percent)

        # Build the training dataset.
        os.mkdir(train_dir)
        train_dir = os.path.join(args.save_dir, 'train')
        print('| Building training data...')
        dataset.build_and_save_dataset(train_dir, image_ids=train_split)

        # Build the validation dataset.
        val_dir = os.path.join(args.save_dir, 'val')
        os.mkdir(val_dir)
        print('| Building validation data...')
        dataset.build_and_save_dataset(val_dir, image_ids=val_split)
