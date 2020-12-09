# -*- coding: utf-8 -*-
"""
Created on Thu Nov 21 10:46:55 2019
@author: marti_cn, ottevan

Trying out different interpolation techiques
For kinging or rbf, use dask: https://stackoverflow.com/questions/51651956/memory-error-by-using-rbf-with-scipy/51712215

"""

import pandas as pd
import numpy as np
from scipy import spatial
import warnings
from scipy.spatial import distance
from scipy.spatial import cKDTree as KDTree 

class SpatialInterpolation(object):
    
    def __init__(self, xiyi, xyz, maxdistance= 20.):
        """
        Input:  xiyi:         location_to_interpolate
                              dataframe containing 2 columns should be named: 'x', 'y'.
                xyz:          dataframe used in the interpolation. 
                              Columnnames should contain: 'x', 'y', 'bedlevel'
                maxdistance:  float value (in meters) that indicates maximum distance between 
                              and data_to_interpolate. 
                              
        Ouptut: 
                 self.xiyi      - stored xiyi data
                 self.xyz       - stored xyz data
                 self.xiyi_tree = kd-tree of xi,yi point pairs for interpolation
                 self.xyz_tree  = kd-tree of x,y,z points with raw data
                 self.dist      = sparse distance matrix between xi,yi and x,y. 
        """
        self.distance = maxdistance
        
        # Selection of points in the grid within a distance given by maxdistance.       
        a = xiyi[['x', 'y']]
        b = xyz[['x', 'y']]
        xmin = np.min(a['x'])
        ymin = np.min(a['y'])
        xmax = np.max(a['x'])
        ymax = np.max(a['y'])
        
        #b = b.drop(b[b['x'] < xmin - maxdistance].index)
        #b = b.drop(b[b['y'] < ymin - maxdistance].index)
        #b = b.drop(b[b['x'] > xmax + maxdistance].index)
        #b = b.drop(b[b['y'] > ymax + maxdistance].index)
        print('Length xiyi:', len(a))
        print('Length xyz:', len(b))

        #steps = 20
        #dx = (xmax-xmin) / steps
        #for k in range(steps): 
        #    a2 = a.copy()
        #    b2 = b.copy()
        #    xlow = xmin + k*dx
        #    xhigh = xmin + (k+1)*dx
        #    a2 = a2.drop(a2[a2['x'] < xlow].index)
        #    a2 = a2.drop(a2[a2['x'] > xhigh].index)
        #    b2 = b2.drop(b2[b2['x'] < xlow - maxdistance].index)
        #    b2 = b2.drop(b2[b2['x'] > xhigh + maxdistance].index)
        #
        #    # Building the trees 
        #    print('Length xiyi step', k, '/', steps, ':', len(a2))
        #    print('Length xyz: step', k, '/', steps, ':', len(b2))
        #    
        leafsize=16 #16=default 
        print('Building kd-tree (1/2)')
        atree = KDTree( a.values, leafsize = leafsize, balanced_tree=False)  # build the tree
        print('Building kd-tree (2/2)')
        btree = KDTree( b.values, leafsize = leafsize, balanced_tree=False)  # build the tree
        
        print('Building distance matrix\n')
        dist = atree.sparse_distance_matrix(btree, maxdistance)
        #print(dist.keys())
        
        #pdb.set_trace()
        # Data in spatialInterpolation class
        self.xiyi = xiyi
        self.xyz  = xyz
        
        self.xiyi_tree = atree
        self.xyz_tree  = btree
        self.dist      = dist
        
        self.maxdistance = maxdistance
                
    def interpolate(self, method='idw'):
        self.method = method
        if method == 'idw': 
            self.interpolate_idw()
        elif method == 'mean': 
            self.interpolate_mean()
        elif method == 'gaussian': 
            self.interpolate_gaussian()
        else: 
            raise ValueError("Interpolation method not in [idw, mean, gaussian]")    

    def interpolate_idw(self):
        """
        Perform inverse distance weighting
        Result is stored in self.result
        """
        index = [j for j in self.dist.keys()]
        a_index = [j[0] for j in index]
        b_index = [j[1] for j in index]
        di = [1/self.dist[j] for j in index]
        bldi = [self.xyz['bedlevel'][j[1]]/self.dist[j] for j in index] 

        df = pd.DataFrame({"i":a_index, 
                           "j":b_index, 
                           "di":di,
                           "bldi":bldi})
        
        table = pd.pivot_table(df, values=['di','bldi'], index=['i'],
                                columns=[], aggfunc={'di': np.sum,
                                                     'bldi': np.sum})
        
        table['idw'] = [table['bldi'][j]/table['di'][j] for j in table.index]
        self.result = table['idw']
     
    def interpolate_mean(self):
        """
        Perform mean bed level
        Result is stored in self.result
        """
        index = [j for j in self.dist.keys()]
        a_index = [j[0] for j in index]
        b_index = [j[1] for j in index]
        bl = [self.xyz['bedlevel'][j[1]] for j in index] 
        
        df = pd.DataFrame({"i":a_index, 
                           "j":b_index, 
                           "bl":bl})
        
        table = pd.pivot_table(df, values=['bl'], index=['i'],
                                columns=[], aggfunc={'bl': np.mean})
        
        #print(table.head())
        table['mean'] = [table['bl'][j] for j in table.index]
        self.result = table['mean']
        
        #print(self.result.head())
        #plt.scatter(self.xiyi['x'][a_index],self.xiyi['y'][a_index],c=df['bl'])
        #plt.show()
        #pdb.set_trace()
        
    def interpolate_gaussian(self):
        """
        Perform weighting by gaussian weighting function
        Result is stored in self.result
        """
        index = [j for j in self.dist.keys()]
        a_index = [j[0] for j in index]
        b_index = [j[1] for j in index]
        
        def weight_function(d,mu=0.0,sigma=self.maxdistance/2.0): 
            return np.exp(-np.floatpower(d-mu,2.0)/(2.0*sigma))
        
        wi = [weight_function(self.dist[j]) for j in index]
        blwi = [self.xyz['bedlevel'][j[1]]*weight_function(self.dist[j]) for j in index] 

        df = pd.DataFrame({"i":a_index, 
                           "j":b_index, 
                           "wi":wi,
                           "blwi":blwi})
        
        table = pd.pivot_table(df, values=['wi','blwi'], index=['i'],
                                columns=[], aggfunc={'wi': np.sum,
                                                     'blwi': np.sum})
        
        table['gaussian'] = [table['blwi'][j]/table['wi'][j] for j in table.index]
        self.result = table['gaussian']
        
        
    def result_to_csv(self, csvfilename):
         d = {'xi': self.xiyi['x'][self.result.index], 
              'yi': self.xiyi['y'][self.result.index], 
              'zi': self.result[self.result.index]}
         df = pd.DataFrame(data=d)
         df.to_csv(csvfilename)

    def result_to_m_n_grid(self):
        #if len(self.result) > 0: 
        #print(self.result)
        d = {'m_coord': self.xiyi['m_coord'][self.result.index], 
             'n_coord': self.xiyi['n_coord'][self.result.index], 
             'x_rd'   : self.xiyi['x_rd'][self.result.index], 
             'y_rd'   : self.xiyi['y_rd'][self.result.index], 
             'zi'     : self.result[self.result.index]}
        #else: 
        #    d = {'m_coord': [], 
        #         'n_coord': [], 
        #         'x_rd'   : [], 
        #         'y_rd'   : [], 
        #         'zi'     : []}
        return pd.DataFrame(data=d)
          

    # def scipy_interpolation(self, method= 'linear'):
        # """
        # Method of interpolation. One of:
        # nearest
            # return the value at the data point closest to the point of interpolation. 
        
        # linear
        # tessellate the input point set to n-dimensional simplices, and interpolate linearly on each simplex. 
        
        # cubic (1-D)
        # return the value determined from a cubic spline.
    
        # cubic (2-D)
        # return the value determined from a piecewise cubic, continuously differentiable (C1), and approximately curvature-minimizing polynomial surface. 
        
        # See https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.griddata.html#scipy.interpolate.griddata
        # for more details.
        
        # Output:
            # dataframe with columns: 'x', 'y', 'interpolated_bedlevel'.
            # You can use the plotting functionality to visualize the results.
        
        # """
        # from scipy.interpolate import griddata    
    
        # interpolation = griddata(self.data_for_interpolation.loc[:,['x','y']].values, 
                                 # self.data_for_interpolation.loc[:,'bedlevel'].values, 
                                 # self.data_to_interpolate.loc[:, ['x', 'y']].values, 
                                 # method= method )
        

        # # Create table with interpolated values
        # self.results= self.data_to_interpolate.loc[:, ['x', 'y', 'm_coord', 'n_coord']].copy()
        # self.results['interpolated_bedlevel'] = interpolation.reshape(len(interpolation), 1) 
    
        # return self.results
    
    
    # def euclidean_norm_numpy(self, x1, x2):
        # return np.linalg.norm(x1 - x2, axis=0)

    # def rbf_interpolation(self, function= 'inverse', epsilon= 0.1, smooth= 0):
        # """
        # Radial Basis Function interpolator instance.
        # Input parameters:
        # Function: String. Can be
            # 'multiquadric': sqrt((r/self.epsilon)**2 + 1)
            # 'inverse': 1.0/sqrt((r/self.epsilon)**2 + 1)
            # 'gaussian': exp(-(r/self.epsilon)**2)
            # 'linear': r
            # 'cubic': r**3
            # 'quintic': r**5
            # 'thin_plate': r**2 * log(r)
       # smooth: float, optional
               # Values greater than zero increase the smoothness 
               # of the approximation. 0 is for interpolation (default), 
               # the function will always go through the nodal points in this case.        
        
        # Output:
            # dataframe with columns: 'x', 'y', 'interpolated_bedlevel'.
            # You can use the plotting functionality to visualize the results.
            
        # LET OP!!!!! Function takes a large amount of time. Better not to use it.
        # """
        
        # from scipy.interpolate import Rbf
        
        # rbfi = Rbf(self.data_for_interpolation.x, 
                   # self.data_for_interpolation.y, 
                   # self.data_for_interpolation.waterdepth,
                   # norm= self.euclidean_norm_numpy,
                   # function= function,
                   # epsilon= epsilon,
                   # smooth= smooth)
        
        # interpolation= rbfi(self.data_to_interpolate.x, self.data_to_interpolate.y)
        
        # # Create table with interpolated values
        # self.results= self.data_to_interpolate.loc[:, ['x', 'y', 'm_coord', 'n_coord']].copy()
        # self.results['interpolated_bedlevel'] = interpolation.reshape(len(interpolation), 1) 
    
        # return self.results
        


    # def idw_interpolation(self, nnear=6, eps=0.1, p=1, stat=1, weights=None ):
        # """
        # Function that does the IDW interpolation.
        # Based on the link: https://stackoverflow.com/questions/3104781/inverse-distance-weighted-idw-interpolation-with-python
        
        # Inputs: q: points in N dimensions wehre I want to make the interpolation
                # nnear: nearest neighbours of each query point in q
                # eps: Smoothing, approximate nearest, dist <= (1 + eps) * true nearest. Default: 0.1
                # p: Factor to determine weiths: weights ~ 1 / distance**p. Default: 1
                # weights: array of predefined weigst of points q.
                # stat: accumulate wsum, wn for average weights. Default: 1

        # Output: 
            # dataframe with columns: 'x', 'y', 'interpolated_bedlevel'.
            # You can use the plotting functionality to visualize the results.
        # """
        # from scipy.spatial import cKDTree as KDTree 
        
        # # Building the tree 
        # leafsize=2 # 
        # X = self.data_for_interpolation.loc[:,['x', 'y']].values
        # z = self.data_for_interpolation['bedlevel'].values
        # q = self.data_to_interpolate.loc[:, ['x', 'y']].values
        
        # tree = KDTree( X, leafsize=leafsize )  # build the tree
       
        # wn = 0
        # wsum = None
        
        # q = np.asarray(q)
        # qdim = q.ndim
        # if qdim == 1:
            # q = np.array([q])
        # if wsum is None:
            # wsum = np.zeros(nnear)

        # distances, ix = tree.query( q, k=nnear, eps=eps )
        # interpol = np.zeros( (len(distances),) + np.shape(z[0]) )
        # jinterpol = 0
        # for dist, IX in zip( distances, ix ):
            # if nnear == 1:
                # wz = z[IX]
            # elif dist[0] < 1e-10:
                # wz = z[IX[0]]
            # else:  # weight z s by 1/dist --
                # w = 1 / dist**p
                # if weights is not None:
                    # w *= weights[IX]  # >= 0
                # w /= np.sum(w)
                # wz = np.dot( w, z[IX] )
                # if stat:
                    # wn += 1
                    # wsum += w
            # interpol[jinterpol] = wz
            # jinterpol += 1
        
        # interpolation = interpol if qdim > 1  else interpol[0]
        # self.results= self.data_to_interpolate.loc[:, ['x', 'y', 'm_coord', 'n_coord']].copy()
        # self.results['interpolated_bedlevel'] = interpolation.reshape(len(interpolation), 1) 
        # #print ( self.results.keys() )
        # return self.results
    
  
