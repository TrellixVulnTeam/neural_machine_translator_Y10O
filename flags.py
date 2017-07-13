import tensorflow as tf
import os
import sys

#==========================Regularization===============================================
#tf.app.flags.DEFINE_boolean("l2_loss", False,
#                            "Not currently implemented. Adds L2 loss term to parameter weights in encoder and attention decoder")
#tf.app.flags.DEFINE_float("l2_loss_lambda", 0.00,
#                           "Not currently implemented. Adds L2 loss term to parameter weights in encoder and attention decoder")



#==========================Basic Execution Options======================================
tf.app.flags.DEFINE_boolean("decode", False,
                            "Set to True for interactive decoding.")

tf.app.flags.DEFINE_boolean("self_test", False,
                            "Run a self-test if this is set to True. Overrides decode flag")



#=================================Learning Rate==============================================
#TODO - abstract this away into a learning rate schedule
tf.app.flags.DEFINE_integer("loss_increases_per_decay", 3,
                            "The learning rate will decay if the loss is greater than the max of the last (this many) checkpoint losses.")

tf.app.flags.DEFINE_float("learning_rate", 0.5, "Learning rate.")

tf.app.flags.DEFINE_float("learning_rate_decay_factor", 0.99,
                          "Learning rate decays by this much.")

tf.app.flags.DEFINE_float("minimum_learning_rate", 0.005, "Minimum learning rate")




#=======================Gradient Clipping====================================================
tf.app.flags.DEFINE_float("max_clipped_gradient", 5.0,
                          "Clip gradients to a maximum of this this norm.")




#=======================Vocabulary File Locations and Save File Locations=======================
tf.app.flags.DEFINE_integer("from_vocab_size", 40000, "Source language vocabulary size.") #20-50k is good

tf.app.flags.DEFINE_integer("to_vocab_size", 40000, "Target language vocabulary size.")

tf.app.flags.DEFINE_string("data_dir", "/home/rob/WMT", "Directory where we will store the data as well as model checkpoint")

tf.app.flags.DEFINE_string("from_train_data", None, "Training data.")

tf.app.flags.DEFINE_string("to_train_data", None, "Training data.")

tf.app.flags.DEFINE_string("from_dev_data", None, "Validation data.")

tf.app.flags.DEFINE_string("to_dev_data", None, "Validation data.")




tf.app.flags.DEFINE_boolean("use_fp16", False,
                            "Train using fp16 instead of fp32.")



#Checkpoint Flags
tf.app.flags.DEFINE_string("checkpoint_name", "translate.ckpt", "Name of the Tensorflow checkpoint file")

tf.app.flags.DEFINE_integer("steps_per_checkpoint", 300, #change me to 300
                            "How many training steps to do per checkpoint.")




#Dataset Flags

#TODO - this right now is useless until i dynamically load datasets.
tf.app.flags.DEFINE_boolean("load_train_set_in_memory", True,
                            "If True, loads training set into memory. Otherwise, reads batches by opening files and reading appropriate lines.")

tf.app.flags.DEFINE_integer("max_train_data_size", 100000,
                            "Limit on the size of training data (0: no limit).")

tf.app.flags.DEFINE_integer("train_offset", 0,
                            "ignore the first train_offset lines of the training file when loading the training set or getting randomly")
#==========================================================================================





#==========================Data Preprocessing Flags===================================
tf.app.flags.DEFINE_integer("max_source_sentence_length", 35, #I like long sentences and tough datasets, so I use 50 and 60 here usually
                            "the maximum number of tokens in the source sentence training example in order for the sentence pair to be able to be used in the dataset")

tf.app.flags.DEFINE_integer("max_target_sentence_length", 45,
                            "the maximum number of tokens in the target sentence training example in order for the sentence pair to be able to be used in the dataset")




#Embedding Flags for Encoder and Decoder
#Was 1024, 512
#===========================Word Embeddings=====================================
tf.app.flags.DEFINE_string("embedding_algorithm", "network",
                            "glove, or network. The first three are unsupervised trainers implemented by other programs. the latter is a network layer trained only by backprop")

tf.app.flags.DEFINE_boolean("train_embeddings", True,
                            "Whether or not to continue training the glove embeddings from backpropagation or to leave them be")

tf.app.flags.DEFINE_integer("encoder_embedding_size", 512,
                            "Number of units in the embedding size of the encoder inputs. This will be used in a wrapper to the first layer")
#Was 1024, 512
tf.app.flags.DEFINE_integer("decoder_embedding_size", 512,
                            "Number of units in the embedding size of the encoder inputs. This will be used in a wrapper to the first layer")

tf.app.flags.DEFINE_string("glove_encoder_embedding_file", "../translator/GloVe/build/rob_vectors_50it_200vec_source.txt",
                            "The output file for Glove-trained word embeddings on the dataset.")

tf.app.flags.DEFINE_string("glove_decoder_embedding_file", "../translator/GloVe/build/rob_vectors_25it_200vec_target.txt",
                            "The output file for Glove-trained word embeddings on the dataset.")




#===========================Parameters==========================================
tf.app.flags.DEFINE_integer("batch_size", 32, #64 would be good, 128 is better.
                            "Batch size to use during training.")


#TODO - add to json, implement and test
tf.app.flags.DEFINE_integer("num_attention_heads", 1,
                            "The number of heads to use in the attention mechanism")


tf.app.flags.DEFINE_integer("sampled_softmax_size", 512, #64 would be good, 128 is better.
                            "Sampled Softmax will use this many logits out of the vocab size for the probability estimate of the true word")

#TODO - decoder vocab boosting is currently not implemented
tf.app.flags.DEFINE_boolean("decoder_vocab_boosting", False,
                            "adaboost decoder prediction weights in the loss function based on perplexities of sentences that contain that word")

tf.app.flags.DEFINE_integer("vocab_boost_occurrence_memory", 100,
                            "When calculating the perpelxity of sentences that contain a certain word, only count that last (this many) sentences with that word")



#==========================================================================================


#decoder_state_initializer's mechanism will depend on the implementation. there are a few different ways of doing it
# essentially, you need to figure out what to do to the decoder state given the last encoder state, either just the top layer of it
# or all layers of it. there are a few options

# 1. "mirror" - take the final state of every layer in the encoder and apply it as the first state of the decoder
#             - THIS ONLY WORKS if you have the exact same number of layers, bidirectional layers, and layer sizes, between encoder and decoder
#
# 2. "top_layer_mirror" - take the final state of the top layer of the encoder and use it for the state of the decoder
#                         at each layer. THIS ONLY WORKS if you have the exact same layer size on the decoder as the top layer
#
# 3. "bahdanu" - take the final state of the top layer of the encoder. if bidirectional, use the BACKWARD STATE ONLY
#                this top state is then multiplied by a trained weight vector with size equal to the sum of the hidden
#                size of each layer of the decoder. finally, this is passed through a hyperbolic tangent.
#                this way, we can create a list of initial states to use in the decoder.
#                this approach will add a trainable weight vector to the parameters.
#
# 4. "nematus" - similar to bahdanu, except using a mean annotation of the hidden states across all time steps of the
#                encoder, not just the final one, multiplied by the trained weight parameter. This does not use the backward direction only, but both
#                concatenated in the event that the top layer of the encoder is bidirectional.
#                this is passed through a hyperbolic tangent as well. 
#
tf.app.flags.DEFINE_string("decoder_state_initializer", "top_layer_mirror",
                           "The strategy used to calculate initial state values for the decoder from the encoder")


#This is where we store the JSON of the encoder and decoder architecture
#See the file encoder_decoder_architecture_help.txt for more information
tf.app.flags.DEFINE_string("encoder_decoder_architecture_json", 'encoder_decoder_architecture.json',
                            "The file name which stores the JSON architecture of the encoder and decoder")


#Dynamic vs Static Encoder and Decoders.
#Dynamic will use calls to the dynamic api and pass sequence length
#Static will use max_time on all network runs, using _PAD symbol, and weighted the padded logits at 0.
tf.app.flags.DEFINE_string("encoder_rnn_api", "dynamic",
                            "must be static or dynamic. if static, uses tensorflow static rnn calls and PAD symbols. if dynamic, uses tensorflow dynamic rnn calls and sequence lengths.")

#TODO - Flesh this out when flags by migrating a few of the tests over from the other code that are common mistakes.
# Alternatively, do absolutely all that we can right here with the flag testing and try to remove them from the model.
def flag_test():
    f = tf.app.flags.FLAGS