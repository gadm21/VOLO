import tensorflow as tf 

import global_config
from LaneNet.LaneNet_model import LaneNet_BackEnd, LaneNet_FrontEnd
from LaneNet.semantic_segmentation_zoo import cnn_basenet

cfg= global_config.cfg



class LaneNet(cnn_basenet.CNNBaseModel):
    
    def __init__(self, phase, reuse= False):
        super(LaneNet, self).__init__()
        self._net_flag= 'vgg'
        self._reuse= reuse

        self._frontend= LaneNet_FrontEnd.LaneNetFrontEnd(phase= phase)
        self._backend= LaneNet_BackEnd.LaneNetBackEnd(phase= phase)

    
    def inference(self, input_tensor, name):

        with tf.variable_scope(name_or_scope= name, reuse= self._reuse):
            #first, extract image feautres
            extract_features_results= self._frontend.bulid_model(input_tensor= input_tensor, name= 'vgg_frontend', reuse= self._reuse)

            #second, apply backend process
            brinay_seg_prediction, instance_seg_prediction= self._backend.inference(
                binary_seg_logits= extract_features_results['binary_seg_logits']['data'],
                instance_seg_logits= extract_features_resultso['instance_seg_logits']['data'],
                name= 'vgg_backend',
                reuse= self._reuse
            )

            self._reuse= True
        
        return binary_seg_prediction, instance_seg_prediction
    


    def compute_loss(self, input_tensor, binary_label, instance_label, name):

        with tf.variable_scope(name_or_scope= name, reuse= self._reuse):
            #first, extract image features
            extract_features_results= self._frontend.build_model(input_tensor= input_tensor, name= 'vgg_frontend', reuse= self._reuse)

            print()
            print()
            print()
            print()
            print("binary_segment_logits:", extract_features_results['binary_segment_logits']['data'].shape)
            #binary segment logits shape: (?, 256, 512, 2)

            print("instance_segment_logits:", extract_features_results['instance_segment_logits']['data'].shape)
            #instance segmnet logits shape: (?, 256, 512, 64)

            #binary segment labels shape: (?, 256, 512, 1)
            #instance segment labels shape: (?, 256, 512, 1)

            #second, apply backend process
            calculated_losses= self._backend.compute_loss(
                binary_seg_logits= extract_features_results['binary_segment_logits']['data'],
                binary_label= binary_label,
                instance_seg_logits= extract_features_results['instance_segment_logits']['data'],
                instance_label= instance_label,
                name= 'vgg_backend',
                reuse= self._reuse
            )

            self._reuse= True
        
        return calculated_losses
