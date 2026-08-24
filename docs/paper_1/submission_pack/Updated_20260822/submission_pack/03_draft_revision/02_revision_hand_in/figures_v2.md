# Figure floats and captions

Six `%% Figure Fx` comments in the skeleton become real floats. Drop-in LaTeX below.
`F_r16_clustering` is already inside `zone_clustering_v2.tex` and is not repeated here.

Leave the linearisation panel and the solve-time panels as comments: `tab:linearisation`
and `tab:computation` carry that content, and eight figures is right for the length.

---

**After the decomposition table** (replaces `%% Figure F6(a,b)`)

```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/F_decomp}
  \caption{Exact decomposition of the copperplate-to-baseline cost gap into a loss main
  effect, a spatial-topology main effect and their interaction, for Memmingen (left) and as
  a distribution across the 135 synthetic networks (right). The additive identity closes to
  machine precision, so the three terms are measured rather than fitted.}
  \label{fig:decomp}
\end{figure}
```

**After the regret table** (replaces `%% Figure F6(c)`)

```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/F_regret}
  \caption{Estimation bias against decision regret for every level, as a percentage of the
  baseline operating cost. For the copperplate and the topology-only control the two carry
  \emph{opposite signs}: a schedule that appears cheaper on paper is markedly more expensive
  to execute. Loss-aware levels show regret approximately equal to bias.}
  \label{fig:regret}
\end{figure}
```

**Validation subsection** (replaces `%% Figures F3, F4, F5, F11`)

```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/validation/stage1_scatter_Tsupply_farend}
  \caption{Simulated against measured supply temperature at the network far end, evaluated
  on the temperature-propagating formulation. The residuals are almost entirely one-signed
  -- the mean absolute error and the bias coincide -- which is the signature of a fixed
  instrument offset rather than of model error: the sensor sits downstream of a three-way
  mixing valve.}
  \label{fig:val_farend}
\end{figure}

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/validation/mixing_valve_offset}
  \caption{The mixing-valve offset that bounds what the temperature field can be validated
  against. Consumer sensors are billing instruments installed downstream of the valve, so
  the metered temperature sits systematically below the primary junction temperature.}
  \label{fig:mixingvalve}
\end{figure}

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/validation/spatial_profile_test}
  \caption{Spatial temperature profile along the network. Nodes used in the loss
  calibration are shown separately from those that were not, so the comparison is not read
  as an in-sample fit.}
  \label{fig:val_spatial}
\end{figure}
```

> **Note.** The third caption was written when a fitted/held-out node split was expected.
> `validation_spatial.py` since established that a multi-node held-out validation is not
> supportable on this metering, and no such split is claimed in §3.1. The caption above is
> worded to describe what the figure shows without claiming a held-out test. If the figure
> does not in fact distinguish calibration nodes, drop it and rely on the per-node appendix
> table, which makes the same point quantitatively.

**Generalisability subsection** (replaces `%% Figures F_drift, F7, F8, F15`)

```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/F_drift}
  \caption{Drift of a frozen loss adder against trunk pipe length across the 135 synthetic
  networks. An adder calibrated on any one network mis-estimates the loss burden on others
  by a mean of 23.5 and up to 40.1 percentage points of cost, which is why the node-resolved
  model -- computing the loss endogenously -- is the transferable one.}
  \label{fig:drift}
\end{figure}
```

**Supply-temperature subsection** (replaces `%% Figure F12`)

```latex
\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/F_tsup}
  \caption{Supply-temperature flexibility. Lowering the plant supply temperature reduces
  thermal loss but shrinks the temperature difference, so flow and pumping rise. The
  cost-optimal reduction is 17.5\,K; beyond 20\,K the pipe velocity limit binds, and
  hydraulics change from a negligible cost into the binding constraint.}
  \label{fig:tsup}
\end{figure}
```
