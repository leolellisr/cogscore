
// File: org/cst/cogscore/modules/motivation/MotivationEvaluationReport.java
package org.cst.cogscore.modules.motivation;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.List;

public final class MotivationEvaluationReport {

    private MotivationEvaluationReport() {
    }

    public static final class TrialResult implements Serializable {
        private static final long serialVersionUID = 1L;

        public int motivationExperimentId = 1;
        public String experimentId = "motivation_experiment";
        public String architectureName = "unknown";
        public int episode = 0;
        public String trialId = "";
        public String condition = "";

        public int targetObject = 0;
        public String targetObjectLabel = "none";
        public String targetRole = "none";

        public int alternativeObject = 0;
        public String alternativeObjectLabel = "none";

        public int controlObject = 0;
        public String controlObjectLabel = "none";

        public int goalObject = 0;
        public String goalObjectLabel = "none";

        public int devaluedObject = 0;
        public String devaluedObjectLabel = "none";

        public String firstRawAction = "";
        public String firstActionCategory = "";
        public String firstFunctionalAction = "";

        public int firstResponseObject = 0;
        public String firstResponseObjectLabel = "none";

        public int firstLookObject = 0;
        public String firstLookObjectLabel = "none";

        public int firstInteractionObject = 0;
        public String firstInteractionObjectLabel = "none";
        public String firstInteractionRole = "none";

        public Long firstLookLatencyCycles = null;
        public Long firstInteractionLatencyCycles = null;
        public Long firstGoalFixLatencyCycles = null;
        public Long firstGoalInteractionLatencyCycles = null;

        public int rawActionCount = 0;
        public int motorActionCount = 0;
        public int virtualActionCount = 0;
        public int attentionalActionCount = 0;

        public int lookCount = 0;
        public int interactionCount = 0;

        public double persistenceDurationCycles = Double.NaN;
        public double persistenceSelectivity = Double.NaN;

        public int resourceChoice = 0;
        public int noveltyChoice = 0;
        public int controlChoice = 0;

        public int substitutionSuccess = 0;
        public double perseveration = Double.NaN;
        public double detourEfficiency = Double.NaN;

        public double inspectionCoverage = Double.NaN;
        public double manipulationCoverage = Double.NaN;
        public int firstAttemptAccuracy = 0;
        public double firstInteractionEfficiency = Double.NaN;

        public double devaluationSensitivity = Double.NaN;
        public double responseSuppression = Double.NaN;

        public boolean omission = false;

        @Override
        public String toString() {
            return "TrialResult{" +
                    "motivationExperimentId=" + motivationExperimentId +
                    ", trialId='" + trialId + '\'' +
                    ", condition='" + condition + '\'' +
                    ", firstRawAction='" + firstRawAction + '\'' +
                    ", firstInteractionObjectLabel='" + firstInteractionObjectLabel + '\'' +
                    ", persistenceSelectivity=" + persistenceSelectivity +
                    ", substitutionSuccess=" + substitutionSuccess +
                    ", firstAttemptAccuracy=" + firstAttemptAccuracy +
                    ", devaluationSensitivity=" + devaluationSensitivity +
                    '}';
        }
    }

    public static final class Summary implements Serializable {
        private static final long serialVersionUID = 1L;

        public int motivationExperimentId = 1;
        public String experimentId = "motivation_experiment";
        public String architectureName = "unknown";
        public int episode = 0;
        public boolean aborted = false;
        public int totalTrials = 0;

        public double meanPersistenceDurationCycles = Double.NaN;
        public double meanPersistenceSelectivity = Double.NaN;

        public double resourceChoiceProbability = Double.NaN;
        public double noveltyChoiceProbability = Double.NaN;
        public double controlChoiceProbability = Double.NaN;

        public double resourceModulationIndex = Double.NaN;
        public double noveltyModulationIndex = Double.NaN;

        public double substitutionSuccessRate = Double.NaN;
        public double meanPerseveration = Double.NaN;
        public double meanDetourEfficiency = Double.NaN;

        public double meanInspectionCoverage = Double.NaN;
        public double meanManipulationCoverage = Double.NaN;
        public double firstAttemptAccuracyRate = Double.NaN;
        public double meanFirstInteractionEfficiency = Double.NaN;

        public double latentLearningGainEfficiency = Double.NaN;
        public double latentLearningGainLatency = Double.NaN;

        public double meanDevaluationSensitivity = Double.NaN;
        public double meanResponseSuppression = Double.NaN;

        public double meanMotorActionCount = Double.NaN;
        public double meanVirtualActionCount = Double.NaN;
        public double meanAttentionalActionCount = Double.NaN;

        public double omissionRate = Double.NaN;
        public double behavioralMotivationScore = Double.NaN;

        public final List<TrialResult> trials = new ArrayList<TrialResult>();

        @Override
        public String toString() {
            return "Summary{" +
                    "motivationExperimentId=" + motivationExperimentId +
                    ", experimentId='" + experimentId + '\'' +
                    ", architectureName='" + architectureName + '\'' +
                    ", episode=" + episode +
                    ", totalTrials=" + totalTrials +
                    ", behavioralMotivationScore=" + behavioralMotivationScore +
                    '}';
        }
    }
}

