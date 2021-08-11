# if ./model/*_FinalModel.pickle exit
    # model =  the latest model
    # if ./data/predict/*_predict.txt exist: # got predict.txt file
        # ...

    # else: # No ./data/predict/*_predict.txt found
        # update log(msg = "No predict file found")
        # check if ./data/new/*_new.txt file exist
            # ...
        # else: # No ./data/new/*_new.txt file found


# else: # No pre-trained model
    # update log(msg="Model not found. No action perfromed")



# TODO: change/ rename one unused data folder into /data/predict