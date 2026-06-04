package org.cst.cogscore.modules.attention;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.List;

public final class AttentionEvaluationReport {

    private AttentionEvaluationReport() {
    }

    public static final class TrialResult implements Serializable {
        private static final long serialVersionUID = 1L;

        public int posnerExperimentId = 1;
        public int episode = 0;
        public String trialId = "";
        public String modality = "attention";

        public AttentionData.CueType cueType = AttentionData.CueType.NEUTRAL;
        public AttentionData.TrialType trialType = AttentionData.TrialType.UNDEFINED;
        public AttentionData.SearchType searchType = AttentionData.SearchType.NONE;

        public int width = 0;
        public int height = 0;
        public int frameCount = 0;

        public Long cueOnsetCycle = null;
        public Long targetOnsetCycle = null;
        public Long detectionCycle = null;
        public Long overtMovementCycle = null;

        public Double reactionTimeCycles = null;
        public Double soaMs = null;
        public Double attentionLatencyCycles = null;
        public Double bottomUpLatencyCycles = null;
        public Double eyeMovementLatencyCycles = null;

        public Integer distractorCount = null;
        public Boolean flanked = null;
        public Double flankerDistance = null;

        public double targetX = Double.NaN;
        public double targetY = Double.NaN;
        public double cueX = Double.NaN;
        public double cueY = Double.NaN;
        public double fixationX = Double.NaN;
        public double fixationY = Double.NaN;
        public double focusX = Double.NaN;
        public double focusY = Double.NaN;

        public double peakValue = Double.NaN;
        public double mapVariance = Double.NaN;
        public double normalizedEntropy = Double.NaN;

        public double initialFidelity = Double.NaN;
        public double finalFidelity = Double.NaN;

        @Override
        public String toString() {
            return "TrialResult{" +
                    "posnerExperimentId=" + posnerExperimentId +
                    ", trialId='" + trialId + '\'' +
                    ", trialType=" + trialType +
                    ", reactionTimeCycles=" + reactionTimeCycles +
                    ", attentionLatencyCycles=" + attentionLatencyCycles +
                    ", bottomUpLatencyCycles=" + bottomUpLatencyCycles +
                    ", finalFidelity=" + finalFidelity +
                    '}';
        }
    }

    public static final class Summary implements Serializable {
        private static final long serialVersionUID = 1L;

        public int posnerExperimentId = 1;
        public String experimentId = "attention_experiment";
        public String architectureName = "unknown";
        public int episode = 0;
        public boolean aborted = false;
        public int totalTrials = 0;

        public double meanRtValid = Double.NaN;
        public double meanRtInvalid = Double.NaN;
        public double meanRtNeutral = Double.NaN;
        public double benefit = Double.NaN;
        public double cost = Double.NaN;
        public double validityEffect = Double.NaN;

        public double meanInitialFidelityOverall = Double.NaN;
        public double meanFinalFidelityOverall = Double.NaN;
        public double meanFinalFidelityValid = Double.NaN;
        public double meanFinalFidelityInvalid = Double.NaN;
        public double meanFinalFidelityNeutral = Double.NaN;

        public Double topDownOrientingLatency = null;
        public final List<Double> soaValues = new ArrayList<Double>();
        public final List<Double> benefitBySoa = new ArrayList<Double>();
        public final List<Double> costBySoa = new ArrayList<Double>();

        public Double meanBottomUpLatency = null;
        public Double meanEyeMovementLatency = null;
        public Double meanRtCued = null;
        public Double meanRtUncued = null;

        public Double featureSearchSlope = null;
        public Double conjunctionSearchSlope = null;

        public final List<Double> flankerDistances = new ArrayList<Double>();
        public final List<Double> crowdingCostByDistance = new ArrayList<Double>();
        public final List<Double> attentionalReductionByDistance = new ArrayList<Double>();

        public final List<TrialResult> trials = new ArrayList<TrialResult>();

        @Override
        public String toString() {
            return "Summary{" +
                    "posnerExperimentId=" + posnerExperimentId +
                    ", experimentId='" + experimentId + '\'' +
                    ", architectureName='" + architectureName + '\'' +
                    ", episode=" + episode +
                    ", totalTrials=" + totalTrials +
                    ", meanRtValid=" + meanRtValid +
                    ", meanRtInvalid=" + meanRtInvalid +
                    ", meanRtNeutral=" + meanRtNeutral +
                    ", benefit=" + benefit +
                    ", cost=" + cost +
                    ", validityEffect=" + validityEffect +
                    ", topDownOrientingLatency=" + topDownOrientingLatency +
                    ", meanBottomUpLatency=" + meanBottomUpLatency +
                    ", meanEyeMovementLatency=" + meanEyeMovementLatency +
                    ", featureSearchSlope=" + featureSearchSlope +
                    ", conjunctionSearchSlope=" + conjunctionSearchSlope +
                    '}';
        }
    }
}