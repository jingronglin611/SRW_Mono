import numpy as np
import scipy.stats
from numba import jit
import matplotlib.pyplot as plt
import time
import numpy.fft as fft

hbar = 6.582119569e-16
c = 299792458

''' Plane wave '''
def Plane_source(E,z0,N=1000,dx=1e-6):
    omega = E/hbar
    wavelength = 2*np.pi*c/omega
    k = omega/c
    x = np.linspace(-N/2,N/2-1,N) * dx
    x,y = np.meshgrid(x,x)
    beam = np.ones(x.shape) * np.exp(-1j * k * z0)
    return beam, x, y

''' Gaussian beam '''
def Gaussian_source(E,w0x,w0y,N,z0):
    omega = E/hbar
    wavelength = 2*np.pi*c/omega
    k = omega/c

    zRx = np.pi*w0x**2/wavelength
    zRy = np.pi*w0y**2/wavelength
    wx = w0x * np.sqrt(1+(z0/zRx)**2)
    wy = w0y * np.sqrt(1+(z0/zRy)**2)
    wmax = np.amax([wx,wy])
    fwhm = 1.18*wmax
    FOV = 4*fwhm
    dx = FOV/N

    x = np.linspace(-N/2, N/2-1, N) * dx
    x,y = np.meshgrid(x,x)
    phase = np.zeros((N,N))

    Rx = z0 * (1+(zRx/z0)**2)
    Ry = z0 * (1+(zRy/z0)**2)

    phase = 2*np.pi/wavelength * np.sqrt(
    (Rx * (1-np.cos(np.arcsin(x/Rx))))**2+
    (Ry * (1-np.cos(np.arcsin(y/Ry))))**2 )

    beam = np.exp(- (x / wx) ** 2 - (y / wy) ** 2) * np.exp(1j * phase)
    return beam, x, y

''' OE '''
# slit
def Slit(beam,x,y,slit_x,slit_y):
    window = (np.abs(x)<slit_x/1e6/2) * (np.abs(y)<slit_y/1e6/2)
    if window.sum() <= 10:
        print('slit too narrow, {} pixels'.format(window.sum()))
    beam_slit = beam * window
    return beam_slit

def Double_slit(beam,x,y,wid,sep):
	window1 = (np.abs(y-sep/2)<=wid/1e6)
	window2 = (np.abs(y+sep/2)<=wid/1e6)
	if window1.sum() + window2.sum() <= 10:
		print('slit too narrow, {} pixels'.format(window1.sum()+window2.sum()))
	beam_slit = beam * (window1+window2)
	return beam_slit

def CircApt(beam,x,y,r):
    window = np.square(x)+np.square(y)<np.square(r)
    if window.sum() <= 10:
        print('slit too narrow, {} pixels'.format(window.sum()))
    beam_slit = beam * window
    return beam_slit

# flat mirror (shape error in progress)
def Mirror(beam,x,y,wavelength, l,alpha,direction='horizontal',shapeError = None, delta=0):
    projectWidth = np.abs(l*np.sin(alpha+delta))
    N,M = np.shape(x)
    shapeError2 = np.zeros(x.shape)
    total_error = np.zeros(x.shape)
    misalign = np.zeros(x.shape)

    if direction == 'horizontal':
        mirror = np.abs(x) < projectWidth
        misalign = delta*x / np.sin(alpha)
    elif direction == 'vertical':
        mirror = np.abs(y) < projectWidth
        misalign = delta*y / np.sin(alpha)
    total_error = shapeError2 * 1e-9 + misalign
    phase = total_error * 4*np.pi * np.sin(alpha) / wavelength
    beam_mirror = beam * mirror * np.exp(1j*phase)

    # flip beam:
    if direction == 'horizontal':
        beam_mirror = np.fliplr(beam_mirror)
    elif direction == 'vertical':
        beam_mirror = np.flipud(beam_mirror)
    return beam_mirror

# lens
def Lens(beam,x,y,k,r,f):
    dx = x[0,1] - x[0,0]
    fxMax = 1.0/(2.0*dx)
    N = x.shape[0]
    dfx = fxMax/N
    fx = np.linspace(-fxMax, fxMax-dfx, N)
    fy = np.copy(fx)
    fx, fy = np.meshgrid(fx,fy)

    # lens aperture
    window = window = np.square(x)+np.square(y)<np.square(r/1e6)
    if window.sum() <= window.size:
        print('lens aperture smaller than beam')
    # lens as FFT
    G = NFFT(beam * window)
    # new axis
    wavelength = 2*np.pi/k
    x1 = fx * wavelength * f
    y1 = fy * wavelength * f
    beam_lens = np.exp(1j*k/2/f * (np.square(x1)+np.square(y1)))/1j/wavelength/f * G
    return beam_lens, x1, y1

# arbitrary optics (n, thickness):
def ArbOpt(beam,x,y,k,optz,n):
    height_max = optz.max()
    delta_phi = k * n * height_max + k * (height_max - optz)
    beam_arbopt = beam*np.exp(1j*delta_phi)
    return beam_arbopt

''' Propagation '''
def Ibeam(input):
    return np.square(input.real)+np.square(input.imag)

def NFFT(input):
    return fft.fftshift(fft.fft2(fft.ifftshift(input)))
def INFFT(input):
    return fft.fftshift(fft.ifft2(fft.ifftshift(input)))

def Drift(beam,x,y,wavelength,dz):
    dx = x[0,1] - x[0,0]
    fxMax = 1.0/(2.0*dx)
    N = x.shape[0]
    dfx = fxMax/N
    fx = np.linspace(-fxMax, fxMax-dfx, N)
    fy = np.copy(fx)
    fx, fy = np.meshgrid(fx,fy)

    k = 2*np.pi/wavelength
    kz = k * (np.sqrt( 1.0 - (wavelength*fx)**2 - (wavelength*fy)**2 ))
    filter0 = fx**2 + fy**2 < (1.0/wavelength)**2

    G = NFFT(beam)
    G = G*np.exp(1j*kz*dz)*filter0
    beam_drift = INFFT(G)
    return beam_drift

def Focus(beam,x,y,wavelength,f):
    dx = x[0,1] - x[0,0]
    fxMax = 1.0/(2.0*dx)
    N = x.shape[0]
    dfx = fxMax/N
    fx = np.linspace(-fxMax, fxMax-dfx, N)
    fy = np.copy(fx)
    fx, fy = np.meshgrid(fx,fy)

    phase = np.exp(1j * np.pi/wavelength/f * (np.square(x)+np.square(y)))

    x1 = fx * wavelength * f
    y1 = fy * wavelength * f

    phase1 = np.exp(1j * np.pi/wavelength/f * (np.square(x1)+np.square(y1)))

    dx1 = x1[0,1] - x1[0,0]
    fxMax1 = 1.0/(2.0*dx1)
    dfx1 = fxMax1/N
    fx1 = np.linspace(-fxMax1, fxMax1-dfx1, N)
    fx1, fy1 = np.meshgrid(fx1,fx1)

    k = 2*np.pi/wavelength
    kz1 = k * (np.sqrt( 1.0 - (wavelength*fx1)**2 - (wavelength*fy1)**2 ))
    filter1 = fx1**2 + fy1**2 < (1.0/wavelength)**2

    beam_focus = NFFT(phase * beam) * phase1
    return beam_focus, x1, y1, kz1, filter1