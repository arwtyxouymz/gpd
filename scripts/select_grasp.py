#! /usr/bin/env python
import rospy
from sensor_msgs.msg import PointCloud2
from sensor_msgs import point_cloud2
import numpy as np
from scipy.linalg import lstsq
from gpd.msg import CloudIndexed, CloudSamples
from std_msgs.msg import Header, Int64
from geometry_msgs.msg import Point
from gpd.msg import GraspConfigList, GraspConfig


# global variable to store the point cloud
cloud = []


def cloudCallback(msg):
    global cloud
    if len(cloud) == 0:
        for p in point_cloud2.read_points(msg):
            cloud.append([p[0], p[1], p[2]])


# Create a ROS node.
rospy.init_node('select_grasp')

# Subscribe to the ROS topic that contains the grasps.
# cloud_sub = rospy.Subscriber('/cloud_pcd', PointCloud2, cloudCallback)
cloud_sub = rospy.Subscriber('/camera/depth_registered/points', PointCloud2, cloudCallback)

# Wait for point cloud to arrive.
while len(cloud) == 0:
    rospy.sleep(0.01)


# Extract the nonplanar indices. Uses a least squares fit AX = b. Plane equation: z = ax + by + c.

np_cloud = np.nan_to_num(np.asarray(cloud))
X = np_cloud
print(X.shape[0])
A = np.c_[X[:, 0], X[:, 1], np.ones(X.shape[0])]
C, _, _, _ = lstsq(A, X[:, 2])
# coefficients of the form: a*x + b*y + c*z + d = 0.
a, b, c, d = C[0], C[1], -1., C[2]
dist = ((a*X[:, 0] + b*X[:, 1] + d) - X[:, 2])**2
err = dist.sum()
idx = np.where(dist > 0.01)


# Publish point cloud and nonplanar indices.
pub = rospy.Publisher('/cloud_indexed', CloudIndexed, queue_size=1)
# pub = rospy.Publisher('/cloud_stitched', CloudIndexed, queue_size=1)

msg = CloudIndexed()
header = Header()
header.frame_id = "/base_link"
header.stamp = rospy.Time.now()
msg.cloud_sources.cloud = point_cloud2.create_cloud_xyz32(header, np_cloud.tolist())
msg.cloud_sources.view_points.append(Point(0, 0, 0))
for i in xrange(np_cloud.shape[0]):
    msg.cloud_sources.camera_source.append(Int64(0))
for i in idx[0]:
    msg.indices.append(Int64(i))
rospy.sleep(3)
pub.publish(msg)
print 'Published cloud with', len(msg.indices), 'indices'


# Select a grasp for the robot to execute.
# global variable to store grasps
grasps = []


def callback(msg):
    global grasps
    grasps = msg.grasps


# Subscribe to the ROS topic that contains the grasps.
grasps_sub = rospy.Subscriber('/detect_grasps/clustered_grasps', GraspConfigList, callback)

# Wait for grasps to arrive.
rate = rospy.Rate(1)

while not rospy.is_shutdown():
    if len(grasps) > 0:
        rospy.loginfo('Received %d grasps.', len(grasps))
        break
# grasps are sorted in descending order by score
grasp = grasps[0]
grasp_pub = rospy.Publisher('/best_grasp', GraspConfig, queue_size=10)
rospy.sleep(1)
grasp_pub.publish(grasp)
print 'Selected grasp with score:', grasp.score
print grasp.top
print grasp.bottom
