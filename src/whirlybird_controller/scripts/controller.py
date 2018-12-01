#!/usr/bin/env python
# license removed for brevity


# This file is a basic structure to write a controller that
# communicates with ROS. It will be the students responsibility
# tune the gains and fill in the missing information

# As an example this file contains PID gains, but other
# controllers use different types of gains so the class
# will need to be modified to accomodate those changes

import rospy
import time
import numpy as np
from whirlybird_msgs.msg import Command
from whirlybird_msgs.msg import Whirlybird
from std_msgs.msg import Float32


class Controller():

    def __init__(self):

        # get parameters
        try:
            param_namespace = '/whirlybird'
            self.param = rospy.get_param(param_namespace)
        except KeyError:
            rospy.logfatal('Parameters not set in ~/whirlybird namespace')
            rospy.signal_shutdown('Parameters not set')
	    print("Key Error Exception thrown!")

        g = self.param['g']
        l1 = self.param['l1']
        l2 = self.param['l2']
        m1 = self.param['m1']
        m2 = self.param['m2']
        d = self.param['d']
        h = self.param['h']
        r = self.param['r']
        Jx = self.param['Jx']
        Jy = self.param['Jy']
        Jz = self.param['Jz']
        km = self.param['km']
	
	#sigma for dirty derivative
	self.sigma = 0.05

        # Roll Gains
        self.P_phi_ = 0.0
        self.I_phi_ = 0.0
        self.D_phi_ = 0.0
        self.Int_phi = 0.0
        self.prev_phi = 0.0

        # Pitch Gains
        self.theta_r = 0.0
        self.P_theta_ = 0.0
        self.I_theta_ = 0.0
        self.D_theta_ = 0.0
        self.prev_theta = 0.0
        self.Int_theta = 0.0

        # Yaw Gains
        self.psi_r = 0.0
        self.P_psi_ = 0.0
        self.I_psi_ = 0.0
        self.D_psi_ = 0.0
        self.prev_psi = 0.0
        self.Int_psi = 0.0

	self.prev_time = rospy.Time.now()

	theta_init = 0.0
	self.dirtyd_theta = 0.0
	self.prev_dirtyd_theta = 0.0
	self.dirtyd_psi = 0.0
	self.prev_dirtyd_psi = 0.0
        self.Fe = (m1*l1 - m2*l2)*g*np.cos(theta_init)/l1     ## we did finish editing this. Right value

        self.command_sub_ = rospy.Subscriber('whirlybird', Whirlybird, self.whirlybirdCallback, queue_size=5)
        self.psi_r_sub_ = rospy.Subscriber('psi_r', Float32, self.psiRCallback, queue_size=5)
        self.theta_r_sub_ = rospy.Subscriber('theta_r', Float32, self.thetaRCallback, queue_size=5)
        self.command_pub_ = rospy.Publisher('command', Command, queue_size=5)
	self.c = 0
        while not rospy.is_shutdown():
            # wait for new messages and call the callback when they arrive
            rospy.spin()


    def thetaRCallback(self, msg):
        self.theta_r = msg.data


    def psiRCallback(self, msg):
        self.psi_r = msg.data

    def whirlybirdCallback(self, msg):
        g = self.param['g']
        l1 = self.param['l1']
        l2 = self.param['l2']
        m1 = self.param['m1']
        m2 = self.param['m2']
        d = self.param['d']
        h = self.param['h']
        r = self.param['r']
        Jx = self.param['Jx']
        Jy = self.param['Jy']
        Jz = self.param['Jz']
        km = self.param['km']

        phi = msg.roll
        theta = msg.pitch
        psi = msg.yaw

        zeta = .7
	tr = 1.4
	numer = 2.2 # .5*np.pi/np.sqrt(1 - zeta**2) # 2.2
	wn = numer/tr
	b0 = 1.152

	tr_lat = .20
	tr_psi = 3
	zeta_lat = .9
	numer_lat = 2.2 #.5*np.pi/np.sqrt(1.0 - zeta_lat**2) #2.2
	wn_lat = numer_lat/tr_lat
	wn_psi = numer_lat/tr_psi

	Fe = (m1*l1 - m2*l2)*g*np.cos(theta)/l1
	bpsi = l2 * self.Fe / (m1*l1**2 + m2*l2**2 + Jz)

	kp_theta = wn**2 / b0
	ki_theta = 3

	kd_theta = 2.0*zeta*wn / b0

	kp_phi = wn_lat**2 * Jx
	ki_phi = 0
	kd_phi = wn_lat * 2.0 * zeta_lat * Jx

	kp_psi = wn_psi**2 / bpsi
	ki_psi = .07
	kd_psi = 2.0*zeta_lat*wn_psi / bpsi 

        # Calculate dt (This is variable)
        now = rospy.Time.now()
        dt = (now-self.prev_time).to_sec()
        self.prev_time = now
        ##################################
        # Controller Implemented here

	#longitudinal	
	error = -theta + self.theta_r
	prev_error = self.prev_theta - self.theta_r
	error_dot = error - prev_error
	theta_dot = (theta - self.prev_theta)/dt

	self.dirtyd_theta = ((2*self.sigma - dt)/(2*self.sigma + dt))*self.prev_dirtyd_theta + 2/(2*self.sigma + dt)*(theta-self.prev_theta)
	
	if(self.dirtyd_theta < 0.1): #integrate error only when the change in theta is small.
		self.Int_theta += (error - prev_error)*dt/2
		print("applying theta int") 

	Ftilde = kp_theta*(error) + ki_theta*self.Int_theta - kd_theta*self.dirtyd_theta
	F = Fe + Ftilde

	#lateral
	error_yaw = -psi + self.psi_r
	prev_error_yaw = self.prev_psi - self.psi_r
	error_yaw_dot = error_yaw - prev_error_yaw
	self.Int_psi += (error_yaw + prev_error_yaw)*dt/2
	psi_dot = (psi - self.prev_psi)/dt

	if(self.dirtyd_psi < 0.1): #integrate error only when the change in theta is small.
		self.Int_psi += (error_yaw - prev_error_yaw)*dt/2
		print("applying psi int")

	phi_r = kp_psi*(error_yaw) + ki_psi*self.Int_psi - kd_psi*psi_dot	

	error_roll = -phi + phi_r
	phi_dot = (phi - self.prev_phi)/dt
	tau = kp_phi * (error_roll) - kd_phi*phi_dot

	# this should be in terms of tau and F.
	T1 = tau / d
	left_force, right_force = F/2+T1, F/2-T1

	self.prev_theta = theta
	self.prev_psi = psi
	self.prev_phi = phi
	self.prev_dirtyd_theta = self.dirtyd_theta
	
	#prints the gains once
	#if(self.c < 1):
	print("kp_theta: ", kp_theta, "kd_theta: ", kd_theta, "kp_phi: ", kp_phi, "kd_phi: ", kd_phi, "kp_psi: ", kp_psi, "kd_psi: ", kd_psi)
	#	self.c += 1

        ##################################

        # Scale Output
        l_out = left_force/km
        if(l_out < 0):
            l_out = 0
        elif(l_out > 0.7):
            l_out = 0.7 

        r_out = right_force/km
        if(r_out < 0):
            r_out = 0
        elif(r_out > 0.7):
            r_out = 0.7

        # Pack up and send command
        command = Command()
        command.left_motor = l_out
        command.right_motor = r_out
        self.command_pub_.publish(command)


if __name__ == '__main__':
    rospy.init_node('controller', anonymous=True)
    controller = Controller()
    try:
        controller = Controller()
    except:
        rospy.ROSInterruptException
    pass
