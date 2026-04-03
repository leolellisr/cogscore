/*
 * Click nbfs://nbhost/SystemFileSystem/Templates/Licenses/license-default.txt to change this license
 * Click nbfs://nbhost/SystemFileSystem/Templates/Classes/Class.java to edit this template
 */
package org.modules.sensorial;

/**
 *
 * @author leolellisr
 */
// modules/sensorial/EvaluationReport.java

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

/**
 * Aggregates results from one or more modality evaluations.
 *
 * The report stores:
 * - per-trial fidelity and distance
 * - mean and standard deviation per delay
 * - fitted decay parameters per modality
 *
 * It also provides simple CSV exports for analysis.
 */
public final class EvaluationReport {

    private final List<ModalityReport> modalities;

    public EvaluationReport(List<ModalityReport> modalities) {
        if (modalities == null) throw new IllegalArgumentException("modalities == null");
        this.modalities = Collections.unmodifiableList(new ArrayList<>(modalities));
    }

    public List<ModalityReport> getModalities() {
        return modalities;
    }

    /**
     * One modality report (e.g., sonar, vision, distance, position) for a single agent.
     */
    public static final class ModalityReport {
        public final String agentId;
        public final String modality;
        public final String metricName;
        public final String cueGeneratorName;

        public final long[] delaysMs;

        // Fidelity and raw distance per [delayIndex][trialIndex]
        public final double[][] fidelity;
        public final double[][] distance;

        // Cue description per [delayIndex][trialIndex]
        public final String[][] cueDescription;

        // Summaries per delay
        public double[] meanFidelity;
        public double[] stdFidelity;

        public double[] meanDistance;
        public double[] stdDistance;

        // Fitted decay model on mean fidelity
        public DecayModelFitter.Params decay;

        public ModalityReport(
                String agentId,
                String modality,
                String metricName,
                String cueGeneratorName,
                long[] delaysMs,
                double[][] fidelity,
                double[][] distance,
                String[][] cueDescription
        ) {
            this.agentId = agentId;
            this.modality = modality;
            this.metricName = metricName;
            this.cueGeneratorName = cueGeneratorName;
            this.delaysMs = delaysMs.clone();
            this.fidelity = fidelity;
            this.distance = distance;
            this.cueDescription = cueDescription;
        }

        /**
         * Computes mean and standard deviation per delay for fidelity and distance.
         * Call this after the runner fills trial matrices.
         */
        public void computeSummaries() {
            int K = delaysMs.length;
            meanFidelity = new double[K];
            stdFidelity = new double[K];
            meanDistance = new double[K];
            stdDistance = new double[K];

            for (int k = 0; k < K; k++) {
                meanFidelity[k] = mean(fidelity[k]);
                stdFidelity[k] = std(fidelity[k], meanFidelity[k]);

                meanDistance[k] = mean(distance[k]);
                stdDistance[k] = std(distance[k], meanDistance[k]);
            }
        }

        /**
         * CSV with one row per (delay, trial).
         */
        public String toCsvPerTrial() {
            StringBuilder sb = new StringBuilder();
            sb.append("agentId,modality,metric,cueGenerator,delayMs,trialIndex,fidelity,distance,cue\n");
            for (int k = 0; k < delaysMs.length; k++) {
                for (int r = 0; r < fidelity[k].length; r++) {
                    sb.append(escape(agentId)).append(',')
                      .append(escape(modality)).append(',')
                      .append(escape(metricName)).append(',')
                      .append(escape(cueGeneratorName)).append(',')
                      .append(delaysMs[k]).append(',')
                      .append(r).append(',')
                      .append(format(fidelity[k][r])).append(',')
                      .append(format(distance[k][r])).append(',')
                      .append(escape(cueDescription[k][r]))
                      .append('\n');
                }
            }
            return sb.toString();
        }

        /**
         * CSV with one row per delay (mean/std).
         */
        public String toCsvSummary() {
            if (meanFidelity == null) computeSummaries();

            StringBuilder sb = new StringBuilder();
            sb.append("agentId,modality,metric,cueGenerator,delayMs,meanFidelity,stdFidelity,meanDistance,stdDistance,F0,lambda,r2,usedPoints\n");
            for (int k = 0; k < delaysMs.length; k++) {
                sb.append(escape(agentId)).append(',')
                  .append(escape(modality)).append(',')
                  .append(escape(metricName)).append(',')
                  .append(escape(cueGeneratorName)).append(',')
                  .append(delaysMs[k]).append(',')
                  .append(format(meanFidelity[k])).append(',')
                  .append(format(stdFidelity[k])).append(',')
                  .append(format(meanDistance[k])).append(',')
                  .append(format(stdDistance[k])).append(',')
                  .append(decay == null ? "" : format(decay.F0)).append(',')
                  .append(decay == null ? "" : format(decay.lambda)).append(',')
                  .append(decay == null ? "" : format(decay.r2)).append(',')
                  .append(decay == null ? "" : Integer.toString(decay.usedPoints))
                  .append('\n');
            }
            return sb.toString();
        }

        private static double mean(double[] v) {
            double s = 0.0;
            for (double x : v) s += x;
            return s / (double) v.length;
        }

        private static double std(double[] v, double mean) {
            if (v.length < 2) return 0.0;
            double s = 0.0;
            for (double x : v) {
                double d = x - mean;
                s += d * d;
            }
            return Math.sqrt(s / (double) (v.length - 1));
        }

        private static String format(double v) {
            if (!Double.isFinite(v)) return "";
            return String.format(Locale.US, "%.6f", v);
        }

        private static String escape(String s) {
            if (s == null) return "";
            String t = s.replace("\"", "\"\"");
            return "\"" + t + "\"";
        }
    }

    /**
     * CSV summary for all modalities (concatenated).
     */
    public String toCsvSummaryAllModalities() {
        StringBuilder sb = new StringBuilder();
        boolean headerWritten = false;

        for (ModalityReport mr : modalities) {
            String csv = mr.toCsvSummary();
            String[] lines = csv.split("\n");
            for (int i = 0; i < lines.length; i++) {
                if (i == 0) {
                    if (!headerWritten) {
                        sb.append(lines[i]).append('\n');
                        headerWritten = true;
                    }
                } else if (!lines[i].trim().isEmpty()) {
                    sb.append(lines[i]).append('\n');
                }
            }
        }
        return sb.toString();
    }
}