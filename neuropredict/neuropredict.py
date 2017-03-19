#/usr/bin/python

import sys
import os
import nibabel
import sklearn
import argparse
import warnings
import pickle
from time import localtime, strftime

from freesurfer import *
from pyradigm import MLDataset
import rhst
import visualize

import config_neuropredict as cfg

def make_time_stamp():
    # # with the minute
    # return  strftime('%Y%m%d-T%H%M',localtime())

    # just by the hour
    return strftime('%Y%m%d-T%H', localtime())

def not_unspecified( var ):
    """ Checks for null values of a give variable! """

    return var not in [ 'None', None, '' ]


def parse_args():
    """Parser/validator for the cmd line args."""

    parser = argparse.ArgumentParser(prog="neuropredict")

    parser.add_argument("-m", "--metadatafile", action="store", dest="metadatafile",
                        default=None, required=True,
                        help="Abs path to file containing metadata for subjects to be included for analysis. At the "
                             "minimum, each subject should have an id per row followed by the class it belongs to. "
                             "E.g. \n"
                             "sub001,control\n"
                             "sub002,control\n"
                             "sub003,disease\n"
                             "sub004,disease\n")

    parser.add_argument("-o", "--outdir", action="store", dest="outdir",
                        required=True,
                        help="Output folder to store features and results.")

    parser.add_argument("-p", "--positiveclass", action="store", dest="positiveclass",
                        default=None,
                        help="Name of the positive class (Alzheimers, MCI or Parkinsons etc) "
                             "to be used in calculation of area under the ROC curve. "
                             "Default: class appearning second in order specified in metadata file.")

    parser.add_argument("-f", "--fsdir", action="store", dest="fsdir",
                        default=None,
                        help="Abs. path of SUBJECTS_DIR containing the finished runs of Freesurfer parcellation")

    parser.add_argument("-a", "--atlas", action="store", dest="atlasid",
                        default="fsaverage",
                        help="Name of the atlas to use for visualization. Default: fsaverage, if available.")

    parser.add_argument("-u", "--userdir", action="store", dest="userdir",
                        default=None,
                        help="Abs. path to an user's own features."
                             "This contains a separate folder for each subject (named after its ID in the metadata "
                             "file) containing a file called features.txt with one number per line. All the subjects "
                             "must have the number of features (#lines in file)")

    parser.add_argument("-t", "--trainperc", action="store", dest="train_perc",
                        default=0.5,
                        help="Percentage of the smallest class to be reserved for training. "
                             "Must be in the interval [0.01 0.99]."
                             "If sample size is sufficiently big, we recommend 0.5."
                             "If sample size is small, or class imbalance is high, choose 0.8.")

    parser.add_argument("-n", "--numrep", action="store", dest="num_rep_cv",
                        default=200,
                        help="Number of repetitions of the repeated-holdout cross-validation. "
                             "The larger the number, the better the estimates will be.")

    if len(sys.argv) < 2:
        print('Too few arguments!')
        parser.print_help()
        parser.exit(1)

    # parsing
    try:
        options = parser.parse_args()
    except:
        parser.exit(1)

    # noinspection PyUnboundLocalVariable
    metadatafile = os.path.abspath(options.metadatafile)
    assert os.path.exists(metadatafile), "Given metadata file doesn't exist."

    if not_unspecified(options.fsdir):
        fsdir = os.path.abspath(options.fsdir)
        assert os.path.exists(fsdir), "Given Freesurfer directory doesn't exist."
        userdir = None
    elif not_unspecified(options.userdir):
        fsdir = None
        userdir = os.path.abspath(options.userdir)
        assert os.path.exists(userdir), "Suppiled input directory for features doesn't exist."
    else:
        raise IOError('One of Freesurfer or user-defined directory must be specified.')

    outdir = os.path.abspath(options.outdir)
    if not os.path.exists(outdir):
        try:
            os.mkdir(outdir)
        except:
            raise

    train_perc = np.float32(options.train_perc)
    assert (train_perc >= 0.01 and train_perc <= 0.99), \
        "Training percentage {} out of bounds - must be > 0.01 and < 0.99".format(train_perc)

    num_rep_cv = np.int64(options.num_rep_cv)
    assert num_rep_cv >= 10, \
        "Atleast 10 repitions of CV is recommened.".format(train_perc)

    return metadatafile, outdir, userdir, fsdir, \
           train_perc, num_rep_cv, options.positiveclass


def get_metadata(path):
    """
    Populates the dataset dictionary with subject ids and classes

    Currently supports the following per line: subjectid,class
    Future plans to include demographics data: subjectid,class,age,sex,education

    """

    sample_ids = list()
    classes = dict()
    with open(path) as mf:
        for line in mf:
            if not line.startswith('#'):
                parts = line.strip().split(',')
                sid = parts[0]
                sample_ids.append(sid)
                classes[sid] = parts[1]

    return sample_ids, classes


def userdefinedget(featdir, subjid):
    """
    Method to read in features for a given subject from a user-defined feature folder. This featdir must contain a
    separate folder for each subject with a file called features.txt with one number per line.

    :param featdir:
    :return: vector of numbers.
    """

    featfile = os.path.join(featdir, subjid, 'features.txt')
    with open(featfile,'r') as fid:
        data = fid.read().splitlines()

    return data, None # TODO no names are associated with user-defined yet!


def getfeatures(subjects, classes, featdir, outdir, outname, getmethod = None):
    """Populates the pyradigm data structure with features from a given method.

    getmethod: takes in a path and returns a vectorized feature set (e.g. set of subcortical volumes),
        with an optional array of names for each feature.
    classes: dict of class labels keyed in by subject id

    """

    assert callable(getmethod), "Supplied getmethod is not callable!" \
                                "It must take in a path and return a vectorized feature set and labels."

    # generating an unique numeric label for each class (sorted in order of their appearance in metadata file)
    class_set = set(classes.values())
    class_labels = dict()
    for idx, cls in enumerate(class_set):
        class_labels[cls] = idx

    ids_excluded = list()

    ds = MLDataset()
    for subjid in subjects:
        try:
            data, feat_names = getmethod(featdir, subjid)
            ds.add_sample(subjid, data, class_labels[classes[subjid]], classes[subjid], feat_names)
        except:
            ids_excluded.append(subjid)
            warnings.warn("Features for {} via {} method could not be read. "
                          "Excluding it.".format(subjid, getmethod.__name__))

    # warning for large number of fails for feature extraction
    if len(ids_excluded) > 0.1*len(subjects):
        warnings.warn('Features for {} subjects could not read. '.format(len(ids_excluded)))
        user_confirmation = raw_input("Would you like to proceed?  y / [N] : ")
        if user_confirmation.lower() not in ['y', 'yes', 'ye']:
            print ('Stopping. \n'
                          'Rerun after completing the feature extraction for all subjects '
                          'or exclude failed subjects..')
            sys.exit(1)
        else:
            print(' Yes. Proceeding with only {} subjects.'.format(ds.num_samples))

    # save the dataset to disk to enable passing on multiple dataset(s)
    savepath = os.path.join(outdir, outname)
    ds.save(savepath)

    return savepath


def saved_dataset_matches(ds_path, subjects, classes):
    """
    Returns True only if the path to dataset
        exists, is not empy,
        contains the same number of samples,
        same sample ids and classes as in meta data!

    :returns bool.
    """

    num_samples = len(subjects)
    num_classes = len(classes)
    if (not os.path.exists(ds_path)) or (os.path.getsize(ds_path) <= 0):
        return False
    else:
        ds = MLDataset(ds_path)
        if ds.num_classes != num_classes or \
                        ds.num_samples != num_samples or \
                        set(ds.class_set) != set(classes) or \
                        set(ds.sample_ids) != set(subjects):
            return False
        else:
            return True


def run_rhst(datasets, outdir):
    """



    :param datasets: dictionary of MLdataset features
    :param outdir: output folder to save the results.
    :return:

    """



def run():
    """Main entry point."""


    metadatafile, outdir, userdir, fsdir, \
        train_perc, num_rep_cv, \
        positiveclass = parse_args()

    subjects, classes = get_metadata(metadatafile)
    # the following loop is required to preserve original order
    # this does not: class_set_in_meta = list(set(classes.values()))
    class_set_in_meta = list()
    for x in classes.values():
        if x not in class_set_in_meta:
            class_set_in_meta.append(x)

    num_samples = len(subjects)
    num_classes = len(class_set_in_meta)
    assert num_classes > 1, \
        "Atleast two classes are required for predictive analysis!" \
        "Only one given ({})".format(set(classes.values()))

    if num_classes == 2:
        if not_unspecified(positiveclass):
            print('Positive class specified for AUC calculation: {}'.format(positiveclass))
        else:
            positiveclass = class_set_in_meta[-1]
            print('Positive class inferred for AUC calculation: {}'.format(positiveclass))

    # let's start with one method/feature set for now
    if not_unspecified(userdir):
        feature_dir = userdir
        method_list = [ userdefinedget ]
    else:
        feature_dir = fsdir
        method_list = [aseg_stats_whole_brain, aseg_stats_subcortical]

    method_names = list()
    outpath_list = list()
    for mm, chosenmethod in enumerate(method_list):
        method_names.append('{}_{}'.format(chosenmethod.__name__,mm)) # adding an index for an even better contrast
        out_name = 'consolidated_{}_{}.MLDataset.pkl'.format(chosenmethod.__name__, make_time_stamp())

        outpath_dataset = os.path.join(outdir, out_name)
        if not saved_dataset_matches(outpath_dataset, subjects, classes):
            # noinspection PyTypeChecker
            outpath_dataset = getfeatures(subjects, classes,
                                          feature_dir,
                                          outdir, out_name,
                                          getmethod = chosenmethod)

        outpath_list.append(outpath_dataset)

    combined_name = '_'.join(method_names)
    dataset_paths_file = os.path.join(outdir, combined_name+ '.list.txt')
    with open(dataset_paths_file, 'w') as dpf:
        dpf.writelines('\n'.join(outpath_list))

    results_file_path = rhst.run(dataset_paths_file, outdir,
                                 train_perc=train_perc,
                                 num_repetitions=num_rep_cv,
                                 pos_class = positiveclass)

    dataset_paths, train_perc, num_repetitions, num_classes, \
        pred_prob_per_class, pred_labels_per_rep_fs, test_labels_per_rep, \
        best_min_leaf_size, best_num_predictors, \
        feature_importances_rf, feature_names, \
        num_times_misclfd, num_times_tested, \
        confusion_matrix, class_order, accuracy_balanced, auc_weighted = \
            rhst.load_results(results_file_path)

    balacc_fig_path = os.path.join(outdir, 'balanced_accuracy')
    visualize.metric_distribution(accuracy_balanced, method_names, balacc_fig_path,
                                  num_classes, "Balanced Accuracy")

    confmat_fig_path = os.path.join(outdir, 'confusion_matrix')
    visualize.confusion_matrices(confusion_matrix, class_order, method_names, confmat_fig_path)

    if num_classes > 2:
        cmp_misclf_fig_path = os.path.join(outdir, 'compare_misclf_rates')
        visualize.compare_misclf_pairwise(confusion_matrix, class_order, method_names, cmp_misclf_fig_path)

    featimp_fig_path = os.path.join(outdir, 'feature_importance')
    visualize.feature_importance_map(feature_importances_rf, method_names, featimp_fig_path, feature_names)

    misclf_out_path = os.path.join(outdir, 'misclassified_subjects')
    visualize.freq_hist_misclassifications(num_times_misclfd, num_times_tested, method_names, misclf_out_path)

if __name__ == '__main__':
    run()