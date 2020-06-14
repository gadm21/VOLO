
import time 
import cv2 
import numpy as np 
from sklearn.cluster import DBSCAN
import os 
import sys 
import random
random.seed(4)
sys.path.append(os.getcwd()) 

def read_image(image_path):
    return cv2.imread(image_path) 

def save_image(save_dir, image_name, image):
    os.makedirs(save_dir, exist_ok=True) 
    cv2.imwrite(os.path.join(save_dir, image_name+".png"), image)

def show_image(image, label= 'r' ):
    cv2.imshow(label, image) 
    cv2.waitKey(0)  
    cv2.destroyWindow(label)

def to_gray(image):

    if len(image.shape) == 3:
        gray_image= cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else: gray_image= image 

    return gray_image 

def to_colored(image):
    if len(image.shape) < 3:
        colored_image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else: colored_image= image

    return colored_image 

def remove_noise(image, min_area_threshold= 500):
    assert len(image.shape) != 3, "remove noise accepts gray images only"

    _, labels, stats, _= cv2.connectedComponentsWithStats(image, connectivity= 8, ltype= cv2.CV_32S)

    for index, stat in enumerate(stats):
        if stat[4] < min_area_threshold:
            noise_indecies= np.where(labels == index)
            image[noise_indecies] = 0

    return image 

def morphological_process(image, kernel_size= 5):
    assert len(image.shape) != 3, "morphological_process accepts gray images only"

    kernel= cv2.getStructuringElement(shape= cv2.MORPH_ELLIPSE, ksize= (kernel_size, kernel_size)) 
    filled_holes_image= cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel, iterations= 1)

    return filled_holes_image 

def resize_image(image, new_size):
    return cv2.resize(image, new_size)

def normalize(image):
    return image / 127.5 - 1.0

def reverse_normalize(image):
    return np.array(image*255, dtype = np.uint8)


class Lane(object):

    def __init__(self, id=0):
        self.color_map= [[0, 0, 255],
                        [0, 255, 0],
                        [255, 0, 0],
                        [255, 255, 0]]
        self.clusters = []
        self.means= [] 
        self.window_h= 5 
        self.id= id 
        self.valid= False 
        self.image_h= None 
        self.image_w= None 
        self.remap_to_x= None 
        self.remap_to_y= None 
        self.lane_curve = None 
        self.birdeye_params = None 
    
    def get_coords(self):
        coords = [] 
        for cluster in self.clusters:
            coords_y, coords_x = cluster
            for y, x in zip(coords_y, coords_x) :
                coords.append((x, y)) 
        return np.array(coords) 

    def mean(self):
        current_mean= (int(np.mean(self.clusters[-1][0])), int(np.mean(self.clusters[-1][1])))
        prev_mean= self.means[-1]

        mean_change= (current_mean[0] - prev_mean[0], current_mean[1] - prev_mean[1]) 
        predicted_mean= (current_mean[0] + mean_change[0] , current_mean[1] + mean_change[1])
        self.means.append(predicted_mean) 

        return predicted_mean    

    def advanced_mean(self):
        current_mean= (np.mean(self.clusters[-1][0]), np.mean(self.clusters[-1][1]))
        prev_mean= self.means[-1]
        mean_change= (current_mean[0] - prev_mean[0], current_mean[1] - prev_mean[1]) 

        new_mean = (current_mean[0] + mean_change[0], int(0.2*prev_mean[1] + 0.8*current_mean[1]))
        self.means.append(new_mean) 
        return new_mean 

    def print_info(self):
        print("lane {:d} info:".format(self.id))
        print("number of pixels on this lane == {:d}".format(self.num_points()))
        print("average cluster width == {:f}".format(self.cluster_width()))
        
        print("mumber of clusters == {:d}".format(len(self.clusters)))
        print("____________________________________________")
        print() 

    def num_points(self):
        total= 0
        for cluster in self.clusters:
            total+= cluster[0].shape[0]
        return int(total)  
    
    def draw_mask(self, shape= None, color_means= False):
        if shape is None:
            shape= ( self.image_h, self.image_w,3 ) 

        mask= np.zeros(shape= shape, dtype= np.uint8)
        mask= self.colorize(mask, self.color_map[self.id%len(self.color_map)], color_means= color_means)
        #mask= resize_image(mask, shape) 
        return mask 

    def colorize(self, image, color, color_means= True):

        if color_means:
            for cluster in self.clusters:

                mean_x = np.mean(cluster[1], dtype=np.int32) 
                mean_y = np.mean(cluster[0], dtype=np.int32) 
                
                cv2.circle(image, (mean_x, mean_y), 1, color, 2)

        else:
            for cluster in self.clusters:
                image[cluster]= color 
            

        return image 

    def cluster_width(self):
        total= 0
        for cluster in self.clusters:
            low_x = np.min(cluster[1])
            high_x= np.max(cluster[1])       
            diff= high_x - low_x
            total+= diff 
        
        last_width = int(np.max(self.clusters[-1][1]) - np.min(self.clusters[-1][1]))
        average_width = int(total // len(self.clusters) )
        weighted_width = int(0.2*average_width + 0.8 * last_width)
        return weighted_width 

    def blacken(self, image) :
        for cluster in self.clusters:
            image[cluster] = 0
    
        return image 

    def get_start_point(self):
        last_mean = self.means[-1] 
        return last_mean[0]

    def complete(self, cluster_coords, image):

        self.clusters.append(cluster_coords) 
        self.means.append((int(np.mean(self.clusters[-1][0])), int(np.mean(self.clusters[-1][1]))))

        self.image_h, self.image_w = image.shape[0], image.shape[1]
        lanes_coords= np.where(image == 255) 
        
        lowest_lane_coord= np.min(lanes_coords[0])
        highest_lane_coord= np.max(cluster_coords[0]) 
        window_center= self.means[-1][1]
        
        
        for window in range(highest_lane_coord, lowest_lane_coord, - self.window_h):
            margin= int(self.cluster_width())

            window_pix= (lanes_coords[0] >= window - self.window_h) & \
                        (lanes_coords[0] < window) & \
                        (lanes_coords[1] > (window_center - margin)) & \
                        (lanes_coords[1] < (window_center + margin))
            lane_coords_within_window = (lanes_coords[0][window_pix], lanes_coords[1][window_pix])
            if lane_coords_within_window[0].shape[0] == 0 : continue  

            self.clusters.append(lane_coords_within_window) 
            window_center= self.mean()[1]

        image= self.blacken(image) 
        #image= remove_noise(image) 
        return image 
             
    def load_remap_matrix(self, remap_file_path):

        assert os.path.exists(remap_file_path), "remap file doesnot exist"

        fs= cv2.FileStorage(remap_file_path, cv2.FILE_STORAGE_READ)
        self.remap_to_x= fs.getNode('remap_ipm_x').mat() 
        self.remap_to_y= fs.getNode('remap_ipm_y').mat()
        fs.release() 
    
    def get_curve(self):
        assert self.valid, 'lane:{:d} is not valid'.format(self.id) 

        ys = []
        xs = []
        for m in self.means:
            ys.append(m[0])
            xs.append(m[1])
        '''
        for cluster in self.clusters:
            for point in cluster:
                ys.append(point[0])
                xs.append(point[1])
        '''
                
        self.lane_curve = np.polyfit(ys, xs, 2)

        #self.lane_curve = np.polyfit(self.means[0], self.means[1], 2) 
        return self.lane_curve 

    def fit(self, remap_file_path = None):
        mask= self.draw_mask(color_means= False) 
        
        self.load_remap_matrix(remap_file_path)
        tmp_mask = resize_image(mask, (720, 1280))
        ipm_mask= cv2.remap(tmp_mask, self.remap_to_x, self.remap_to_y, interpolation= cv2.INTER_NEAREST)
       
        nonzero_y = np.array(ipm_mask.nonzero()[0]) 
        nonzero_x = np.array(ipm_mask.nonzero()[1]) 
        params = 0 #np.polyfit(nonzero_y, nonzero_x, 2) 
        
        return mask, ipm_mask, params
      




class PostProcessor(object):

    def __init__(self, ipm_remap_file_path='files/tusimple_ipm_remap.yml'):
        
        self.ipm_remap_file_path = ipm_remap_file_path 

        self.stride_h= -5
        self.lane_id= 0
        
        self.color_map= [[0, 0, 255],
                        [0, 255, 0],
                        [255, 0, 0],
                        [255, 255, 0]]


        self.dbscan_eps= 8
        self.dbscan_min_samples= 30
        self.db= DBSCAN(self.dbscan_eps, self.dbscan_min_samples) 
        self.lane_acceptance_factor= 0.4
    
    def give_id(self):
        self.lane_id+= 1
        return self.lane_id 

    def pre_processing(self, image):
        image= to_gray(image) 
        image= remove_noise(image) 
        image= morphological_process(image) 
        return image 

    def inspect_lanes(self, lanes):
        total_points= 0
        for lane in lanes:
            total_points+= lane.num_points()
        average_lane_points= total_points / len(lanes)
        min_lane_points= average_lane_points * self.lane_acceptance_factor

        for lane in lanes:
            if lane.num_points() > min_lane_points:
                lane.valid= True 
        
    def apply_clustering_on_stride(self, coords):

        ret= self.db.fit(np.array(coords).transpose())
        labels= ret.labels_
        unique_labels= np.unique(labels) 
        return labels, unique_labels 

    def process(self, binary, source):
        
        if int(np.max(binary)) != 255 : binary = np.array(binary*255, dtype = np.uint8)
        image= self.pre_processing(binary) 
        #image = resize_image(binary, (1280, 720) )
        #image_h, image_w = image.shape
        
        lanes_coords= np.where(image == 255) 
        assert len(lanes_coords[0]), 'no lanes to process' 

        lowest_lane_coord= np.min(lanes_coords[0])
        highest_lane_coord= np.max(lanes_coords[0]) 
        
        lanes= []
        lanes_params = [] 

        for stride in range(highest_lane_coord, lowest_lane_coord, self.stride_h):
            lanes_coords= np.where(image == 255)
            target_within_stride= (lanes_coords[0] < stride) & (lanes_coords[0] >= (stride + self.stride_h))
            stride_lanes_coords= (lanes_coords[0][target_within_stride], lanes_coords[1][target_within_stride])
            
            if stride_lanes_coords[0].shape[0] == 0 : continue 

            labels, unique_labels= self.apply_clustering_on_stride(stride_lanes_coords) 
            for label in unique_labels:
                if label==-1:  continue             
                cluster= (labels == label)
                cluster_coords= (stride_lanes_coords[0][cluster], stride_lanes_coords[1][cluster])
                
                lane= Lane(self.give_id()) 
                
                image= lane.complete(cluster_coords, image) 
                
                lanes.append(lane) 
                
        self.inspect_lanes(lanes) 

        mask = np.zeros((720, 1280, 3), dtype = np.uint8) 
        
        lane_counter = 0
        for lane in lanes :
            if not lane.valid : continue 
            lane_counter += 1
            coords = lane.get_coords() 
            coords_y = np.int_(coords[:,1]) 
            coords_x = np.int_(coords[:,0])
            start_point = np.min(coords_y) 
            end_point = np.max(coords_y) 
            
            params = np.polyfit(coords_y, coords_x, 2) 
            lanes_params.append(params) 
            
            poly_coords_y = np.int_(np.linspace(start_point, end_point , end_point - start_point)) 
            poly_coords_x = np.int_(np.clip(params[0]*poly_coords_y**2 + params[1]*poly_coords_y + params[2], 0, 1280-1) )
            color = self.color_map[self.give_id()%len(self.color_map)]
            
            mask[(poly_coords_y, poly_coords_x)] = color 
        if lane_counter > 5 : print("WARNING | {} lanes detected".format(lane_counter) )
        
        ret = {
            'mask_image': mask,
            'lanes_params': lanes_params,
        }

        return ret 
        





