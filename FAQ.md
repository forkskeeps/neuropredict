# neuropredict FAQ

## Frequently Asked Questions

* _What is the overarching goal for neuropredict?_
  * To offer a comprehensive report on predictive analysis effortlessly!
  * Aiming to interface directly with the outputs of various neuroimaging tools
    * **although the user could input arbitrary set of features (neuroimaging, astronomy, nutrition, phrama or otherwise).**
* _What is your classification system?_
  * Predictive analysis is performed with Random Forest classifier (using scikit-learn's implementation) 
  * Model selection (grid search of optimal hyper parameters) is performed in an inner cross-validation.
* _Why random forests?_
  * Because they have consistently demonstrated top performance across multiple domains:
    * [Fernández-Delgado, M., Cernadas, E., Barro, S., & Amorim, D. (2014). Do we Need Hundreds of Classifiers to Solve Real World Classification Problems? Journal of Machine Learning Research, 15, 3133–3181.](http://jmlr.org/papers/volume15/delgado14a/delgado14a.pdf)
    * Lebedev, A. V., Westman, E., Van Westen, G. J. P., Kramberger, M. G., Lundervold, A., Aarsland, D., et al. (2014). Random Forest ensembles for detection and prediction of Alzheimer's disease with a good between-cohort robustness. NeuroImage: Clinical, 6, 115–125. http://doi.org/10.1016/j.nicl.2014.08.023
  * Because it's multi-class by design and automatically estimates feature importance.
* _What are the options for my feature selection?_
  * Currently `neuropredict` selects the top `k = n_min/10` features based on their variable importance, as computed by Random Forest classifier, where n_min = number of *training* samples in the *smallest* class. This choice helped alleviate class-imbalance problems as well as improve the robustness of the classifier.
  * We plan to implement offer more choices for feature selection in the near future, although the benefit of trying some arbitrary choice for feature selection method seems unclear. The overarching goals of `neuropredict` might help answer the current choice:
    * to enable novice predictive modeling users to get started easily and quickly,
    * provide a thorough estimate of *baseline* performance of their feature sets, instead of trying to find an arbitrary combination of predictive modeling tools to drive the numerical performance as high as possible.
  * Also because Random forest classifier automatically discard features without any useful signal.
  * `neuropredict` is designed such that another classifier or combination of classifiers could easily be plugged in. We may be adding an option to integrate one of the following options to automatically select a classifier with the highest performance: [scikit-optimize](https://github.com/scikit-optimize/scikit-optimize), [auto_ml](https://github.com/ClimbsRocks/auto_ml) and [tpot](https://github.com/rhiever/tpot) etc.
  
* _Does `neuropredict` handle covariates?_
  * Not yet. This feature request is not trivial to implement, as the nature of covariate handling is complex and variety of methods is large.
  * If you need to, please regress them out (or handle them using another method of your choice) prior to inputting the features.

* _Can I get ROC curves?_
  * Not at the moment, as the presented results and report is obtained from a large number of CV iterations and there is not one ROC curve to represent it all.
  * It is indeed possible to *"average"* ROC curves from multiple iterations (see below) and visualize it. This feature will be added soon.
    * Fawcett, T. (2006). An introduction to ROC analysis. Pattern Recognition Letters, 27(8), 861–874.
  * For multi-class classification problems, ROC analysis (hyper-surface to be precise) becomes intractable quickly. The author is currently not aware of any easy solutions. if you are aware of any solutions or could contribute, it would be greatly appreciated.
  
* _Can I compare an arbitrary set of my own custom-designed features?_
  * Yes. The -u option allows you to supply arbitrary set of paths to user's own custom features e.g. `-u /myproject/awsome-new-idea-v2.0 /myproject/awsome-new-idea-v1 /myproject/DTI_FA_Method1 /myproject/resting-dynamic-fc /prevproject/resting-dynamic-fc-competingmethod`
  
* _Can I combine `-f` option with `-u` to compare my own features with that of Freesurfer or other supported software?_
  * Absolutely. 
  * While `-f` option allows specifying only 1 freesurfer folder, it can be combined with `-u` which can take arbitray number of custom features.
  
   
