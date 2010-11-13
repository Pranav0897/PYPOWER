# Copyright (C) 1996-2010 Power System Engineering Research Center
# Copyright (C) 2010 Richard Lincoln <r.w.lincoln@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License")
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from numpy import real, imag, exp, angle, zeros, r_, conj, linalg, Inf
from numpy import flatnonzero as find

from scipy.sparse import hstack, vstack
from scipy.sparse.linalg import spsolve, splu

from pypower.dSbus_dV import dSbus_dV
from pypower.makeSbus import makeSbus
from pypower.idx_bus import PD, QD

def cpf_predict(Ybus, ref, pv, pq, V, lmbda, sigma, type_predict, initQPratio,
                loadvarloc, flag_lmbdaIncrease):
    """Do prediction in CPF.

    @author: Rui Bo
    @author: Richard Lincoln
    @see: U{http://www.pserc.cornell.edu/matpower/}
    """
    pvpq = pv + pq

    ## set up indexing
    npv = len(pv)
    npq = len(pq)

    pv_bus = len(find(pv == loadvarloc)) > 0

    ## form current variable set from given voltage
    x_current = r_[ angle(V[pvpq]),
                    abs(V(pq)),
                    lmbda ]

    ## evaluate Jacobian
    dSbus_dVm, dSbus_dVa = dSbus_dV(Ybus, V)

    j11 = real(dSbus_dVa([pvpq], [pvpq]))
    j12 = real(dSbus_dVm([pvpq], pq))
    j21 = imag(dSbus_dVa(pq, [pvpq]))
    j22 = imag(dSbus_dVm(pq, pq))

    J = vstack([
            hstack([j11, j12]),
            hstack([j21, j22])
        ], format="csr")

    ## form K
    K = zeros(npv + 2 * npq)
    if pv_bus: # pv bus
        K[find(pv == loadvarloc)] = -1                         # corresponding to deltaP
    else: # pq bus
        K[npv + find(pq == loadvarloc)] = -1                   # corresponding to deltaP
        K[npv + npq + find(pq == loadvarloc)] = -initQPratio   # corresponding to deltaQ


    ## form e
    e = zeros((1, npv+2*npq+1))
    if type_predict == 1: # predict voltage
        if flag_lmbdaIncrease == True:
            e[npv + 2 * npq + 1] = 1 # dlmbda = 1
        else:
            e[npv + 2 * npq + 1] = -1 # dlmbda = -1
    elif type_predict == 2: # predict lmbda
        e[npv + npq + find(pq == loadvarloc)] = -1 # dVm = -1
    else:
        raise ValueError, "Error: unknown 'type_predict.\n"

    ## form b
    b = zeros(npv + 2 * npq + 1)
    b[npv + 2 * npq + 1] = 1

    ## form augmented Jacobian
    #NOTE: the use of '-J' instead of 'J' is due to that the definition of
    #dP(,dQ) in the textbook is the negative of the definition in MATPOWER. In
    #the textbook, dP=Pinj-Pbus In MATPOWER, dP=Pbus-Pinj. Therefore, the
    #Jacobians generated by the two definitions differ only in the sign.

    augJ = vstack([
            hstack([-J, K]),
            e
        ], format="csr")

    ## calculate predicted variable set
    x_predicted = x_current + sigma * spsolve(augJ, b)

    ## convert variable set to voltage form
    V_predicted[ref] = V[ref]
    V_predicted[pv] = abs(V[pv]) * exp(1j * x_predicted[:npv] )
    V_predicted[pq] = x_predicted[npv + npq + 1:npv + 2 * npq] * exp(1j * x_predicted[npv + 1:npv + npq])
    lmbda_predicted = x_predicted[npv + 2 * npq + 1]

    return V_predicted, lmbda_predicted, J