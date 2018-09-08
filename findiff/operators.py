from findiff.coefs import coefficients, coefficients_non_uni
import numpy as np


class Operator(object):
    pass


class UnaryOperator(Operator):
    pass


class BinaryOperator(Operator):
    pass


class PartialDerivative(UnaryOperator):

    def __init__(self, *args):
        """ Representation of a general partial derivative 
         
                \frac{\partial^(n_i + n_j + ... + n_k) / \partial}
                     {\partial x_i^n_i \partial x_j^n_j ... \partial x_k^_k}
            
            This class does not know anything about discrete grids.
            
            args:
            -----
                   A list of tuples of the form
                         (axis, derivative order)
                         
                   If the list contained only one tuple, you can skip the tuple parentheses.
                   
                   An empty argument list is equivalent to the identity operator.
                              
         """

        tuples = self._convert_to_valid_tuple_list(args)
        self.derivs = {}
        for t in tuples:
            if t[0] in self.derivs:
                raise ValueError("Derivative along axis %d specified more than once." % (t[0]))
            self.derivs[t[0]] = t[1]

    def axes(self):
        return sorted(list(self.derivs.keys()))

    def order(self, axis):
        if axis in self.derivs:
            return self.derivs[axis]
        return 0

    def apply(self, fd, u):

        for axis, order in self.derivs.items():
            if fd.is_uniform():
                u = self._diff(u, fd.spac[axis], order, axis, coefficients(order, fd.acc))
            else:
                coefs = []
                for i in range(len(fd.coords[axis])):
                    coefs.append(coefficients_non_uni(order, fd.acc, fd.coords[axis], i))
                u = self._diff_non_uni(u, fd.coords[axis], axis, coefs)

        return u

    def _diff(self, y, h, deriv, dim, coefs):
        """The core function to take a partial derivative on a uniform grid.
        """

        npts = y.shape[dim]

        scheme = "center"
        weights = coefs[scheme]["coefficients"]
        offsets = coefs[scheme]["offsets"]

        nbndry = len(weights) // 2
        ref_slice = slice(nbndry, npts - nbndry, 1)
        off_slices = [self._shift_slice(ref_slice, offsets[k], npts) for k in range(len(offsets))]

        yd = np.zeros_like(y)

        self._apply_to_array(yd, y, weights, off_slices, ref_slice, dim)

        scheme = "forward"
        weights = coefs[scheme]["coefficients"]
        offsets = coefs[scheme]["offsets"]

        ref_slice = slice(0, nbndry, 1)
        off_slices = [self._shift_slice(ref_slice, offsets[k], npts) for k in range(len(offsets))]

        self._apply_to_array(yd, y, weights, off_slices, ref_slice, dim)

        scheme = "backward"
        weights = coefs[scheme]["coefficients"]
        offsets = coefs[scheme]["offsets"]

        ref_slice = slice(npts - nbndry, npts, 1)
        off_slices = [self._shift_slice(ref_slice, offsets[k], npts) for k in range(len(offsets))]

        self._apply_to_array(yd, y, weights, off_slices, ref_slice, dim)

        h_inv = 1. / h ** deriv
        return yd * h_inv

    def _diff_non_uni(self, y, coords, dim, coefs):
        """The core function to take a partial derivative on a non-uniform grid"""

        yd = np.zeros_like(y)

        ndims = len(y.shape)
        multi_slice = [slice(None, None)] * ndims
        ref_multi_slice = [slice(None, None)] * ndims

        for i, x in enumerate(coords):
            weights = coefs[i]["coefficients"]
            offsets = coefs[i]["offsets"]
            ref_multi_slice[dim] = i

            for off, w in zip(offsets, weights):
                multi_slice[dim] = i + off
                yd[ref_multi_slice] += w * y[multi_slice]

        return yd

    def _apply_to_array(self, yd, y, weights, off_slices, ref_slice, dim):
        """Applies the finite differences only to slices along a given axis"""

        ndims = len(y.shape)

        all = slice(None, None, 1)

        ref_multi_slice = [all] * ndims
        ref_multi_slice[dim] = ref_slice

        for w, s in zip(weights, off_slices):
            off_multi_slice = [all] * ndims
            off_multi_slice[dim] = s
            if abs(1 - w) < 1.E-14:
                yd[ref_multi_slice] += y[off_multi_slice]
            else:
                yd[ref_multi_slice] += w * y[off_multi_slice]

    def _shift_slice(self, sl, off, max_index):

        if sl.start + off < 0 or sl.stop + off > max_index:
            raise IndexError("Shift slice out of bounds")

        return slice(sl.start + off, sl.stop + off, sl.step)

    def _convert_to_valid_tuple_list(self, args):

        all_are_tuples = True
        for arg in args:
            if not isinstance(arg, tuple):
                all_are_tuples = False
                break

        if all_are_tuples:
            all_tuples = args
        else:
            if len(args) > 2:
                raise ValueError("Too many arguments. Did you mean tuples?")
            all_tuples = [(args[0], args[1])]

        for t in all_tuples:
            self._assert_tuple_valid(t)

        return all_tuples

    def _assert_tuple_valid(self, t):
        if len(t) > 2:
            raise ValueError("Too many arguments in tuple.")
        axis, order = t
        if not isinstance(axis, int) or axis < 0:
            raise ValueError("Axis must be non-negative integer")
        if not isinstance(order, int) or order <= 0:
            raise ValueError("Derivative order must be positive integer")


class Plus(Operator):

    def __init__(self, left, right):
        self.left = left
        self.right = right

    def apply(self, fd, u):
        u_left = self.left.apply(fd, u)
        u_right = self.right.apply(fd, u)
        return u_left + u_right


class Multiply(Operator):

    def __init__(self, left, right):
        self.left = left
        self.right = right

    def apply(self, fd, u):
        return self.left * self.right.apply(fd, u)

