/*
 * Click nbfs://nbhost/SystemFileSystem/Templates/Licenses/license-default.txt to change this license
 * Click nbfs://nbhost/SystemFileSystem/Templates/Classes/Class.java to edit this template
 */
package org.modules.sensorial;

/**
 *
 * @author leolellisr
 */
// modules/sensorial/DecayModelFitter.java

/**
 * Fits a simple exponential decay model to mean fidelity vs. delay:
 *
 *   F(t) = F0 * exp(-lambda * t)
 *
 * We fit using a log-linear least squares approximation:
 *   ln(F(t)) = ln(F0) - lambda * t
 *
 * Practical notes:
 * - We ignore non-positive fidelity values when fitting (since ln(F) is undefined).
 * - Time is in milliseconds; lambda will be in 1/ms.
 */
public final class DecayModelFitter {

    private DecayModelFitter() { }

    public static final class Params {
        public final double F0;
        public final double lambda;
        public final double r2;
        public final int usedPoints;

        public Params(double f0, double lambda, double r2, int usedPoints) {
            this.F0 = f0;
            this.lambda = lambda;
            this.r2 = r2;
            this.usedPoints = usedPoints;
        }

        public double predict(long tMs) {
            return F0 * Math.exp(-lambda * (double) tMs);
        }

        @Override
        public String toString() {
            return "Params{F0=" + F0 + ", lambda=" + lambda + ", r2=" + r2 + ", usedPoints=" + usedPoints + "}";
        }
    }

    /**
     * Fits F(t) = F0 * exp(-lambda t) using log-linear regression on mean fidelities.
     *
     * @param delaysMs delays in milliseconds
     * @param meanFidelities mean fidelity for each delay (same length as delaysMs)
     */
    public static Params fitExponential(long[] delaysMs, double[] meanFidelities) {
        if (delaysMs == null || meanFidelities == null) throw new IllegalArgumentException("null input");
        if (delaysMs.length != meanFidelities.length) throw new IllegalArgumentException("length mismatch");
        if (delaysMs.length < 2) return new Params(Double.NaN, Double.NaN, Double.NaN, 0);

        // Collect valid points (F > 0).
        int n = 0;
        for (double f : meanFidelities) {
            if (f > 0 && Double.isFinite(f)) n++;
        }
        if (n < 2) return new Params(Double.NaN, Double.NaN, Double.NaN, n);

        double[] x = new double[n];
        double[] y = new double[n]; // ln(F)
        int idx = 0;
        for (int i = 0; i < delaysMs.length; i++) {
            double f = meanFidelities[i];
            if (f > 0 && Double.isFinite(f)) {
                x[idx] = (double) delaysMs[i];
                y[idx] = Math.log(f);
                idx++;
            }
        }

        // Ordinary least squares for y = a + b*x
        double xMean = mean(x);
        double yMean = mean(y);
        double sxx = 0.0;
        double sxy = 0.0;
        for (int i = 0; i < n; i++) {
            double dx = x[i] - xMean;
            double dy = y[i] - yMean;
            sxx += dx * dx;
            sxy += dx * dy;
        }

        if (sxx == 0.0) return new Params(Double.NaN, Double.NaN, Double.NaN, n);

        double b = sxy / sxx;        // slope
        double a = yMean - b * xMean; // intercept

        double F0 = Math.exp(a);
        double lambda = -b;

        // Compute R^2 in log-space.
        double ssTot = 0.0;
        double ssRes = 0.0;
        for (int i = 0; i < n; i++) {
            double yi = y[i];
            double yHat = a + b * x[i];
            ssTot += (yi - yMean) * (yi - yMean);
            ssRes += (yi - yHat) * (yi - yHat);
        }
        double r2 = (ssTot == 0.0) ? Double.NaN : (1.0 - ssRes / ssTot);

        return new Params(F0, lambda, r2, n);
    }

    private static double mean(double[] v) {
        double s = 0.0;
        for (double x : v) s += x;
        return s / (double) v.length;
    }
}