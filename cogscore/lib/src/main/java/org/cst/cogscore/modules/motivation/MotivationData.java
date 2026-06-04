// File: org/cst/cogscore/modules/motivation/MotivationData.java
package org.cst.cogscore.modules.motivation;

import org.cst.cogscore.modules.motivation.MotivationActionSet.ActionId;
import org.cst.cogscore.modules.motivation.MotivationActionSet.FunctionalType;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import static org.cst.cogscore.modules.motivation.MotivationData.Phase.values;

public final class MotivationData {

    private MotivationData() {
    }

    public enum Phase {
        INIT(-1),
        ITI(0),
        BASELINE(1),
        ELICITATION(2),
        REMOVAL(3),
        PERSISTENCE(4),
        CHOICE(5),
        FAMILIARIZATION(6),
        BLOCKED_TEST(7),
        EXPLORATION(8),
        REWARD_INTRO(9),
        PROBE(10),
        TRAINING(11),
        DEVALUATION(12),
        EXTINCTION(13),
        UNKNOWN(999);

        public final int code;

        Phase(int code) {
            this.code = code;
        }

        public static Phase fromCode(int code) {
            for (Phase p : values()) {
                if (p.code == code) {
                    return p;
                }
            }
            return UNKNOWN;
        }
    }

    public static final class ObjectContext implements Serializable {
        private static final long serialVersionUID = 1L;

        public int index = 0;
        public String name = "";
        public String label = "";
        public String role = "";

        public double x = Double.NaN;
        public double y = Double.NaN;
        public double z = Double.NaN;

        public boolean target = false;
        public boolean alternative = false;
        public boolean goal = false;
        public boolean blocked = false;
        public boolean devalued = false;
        public boolean rewarded = false;

        public boolean labelOrRoleContains(String query) {
            if (query == null) {
                return false;
            }

            String q = query.trim().toLowerCase();

            return label != null && label.toLowerCase().contains(q)
                    || role != null && role.toLowerCase().contains(q)
                    || name != null && name.toLowerCase().contains(q);
        }

        @Override
        public String toString() {
            return "ObjectContext{" +
                    "index=" + index +
                    ", label='" + label + '\'' +
                    ", role='" + role + '\'' +
                    ", target=" + target +
                    ", alternative=" + alternative +
                    ", goal=" + goal +
                    ", blocked=" + blocked +
                    ", devalued=" + devalued +
                    ", rewarded=" + rewarded +
                    '}';
        }
    }

    public static final class TrialContext implements Serializable {
        private static final long serialVersionUID = 1L;

        public boolean ready = false;
        public int episode = 0;
        public int trial = 0;
        public String trialId = "";

        public int experimentId = 1;
        public String experimentName = "motivation_experiment";

        public Phase phase = Phase.UNKNOWN;
        public String phaseLabel = "";
        public long currentCycle = 0L;
        public long phaseStartCycle = -1L;

        public int developmentalPhase = 3;

        public String condition = "none";
        public int conditionCode = 0;

        public int targetObject = 0;
        public String targetLabel = "none";
        public String targetRole = "none";

        public int alternativeObject = 0;
        public String alternativeLabel = "none";

        public int controlObject = 0;
        public String controlLabel = "none";

        public int goalObject = 0;
        public String goalLabel = "none";

        public int devaluedObject = 0;
        public String devaluedLabel = "none";

        public boolean targetRemoved = false;
        public boolean objectBlocked = false;
        public boolean rewardAvailable = false;
        public boolean outcomeDevalued = false;
        public boolean explorationAllowed = false;
        public boolean trialComplete = false;
        public boolean allDone = false;

        public int lastResponseSeq = -1;
        public int lastResponseObject = 0;
        public int lastResponseAction = 0;

        public int objectCount = 0;
        public final List<ObjectContext> objects = new ArrayList<ObjectContext>();

        public boolean isValidObjectIndex(int index) {
            return index >= 1 && index <= objectCount;
        }

        public ObjectContext objectByIndex(int index) {
            for (ObjectContext o : objects) {
                if (o.index == index) {
                    return o;
                }
            }
            return null;
        }

        public String objectLabel(int index) {
            ObjectContext o = objectByIndex(index);
            return o == null ? "none" : o.label;
        }

        public String objectRole(int index) {
            ObjectContext o = objectByIndex(index);
            return o == null ? "none" : o.role;
        }

        public int findObjectIndexByLabelOrRole(String query) {
            for (ObjectContext o : objects) {
                if (o.labelOrRoleContains(query)) {
                    return o.index;
                }
            }
            return 0;
        }

        public int findObjectIndexByColor(String color) {
            if (color == null) {
                return 0;
            }

            String q = color.trim().toLowerCase();

            for (ObjectContext o : objects) {
                if (o.labelOrRoleContains(q)) {
                    return o.index;
                }
            }

            return 0;
        }

        public int firstGoalOrTargetObject() {
            if (isValidObjectIndex(goalObject)) {
                return goalObject;
            }

            if (isValidObjectIndex(targetObject)) {
                return targetObject;
            }

            return 0;
        }

        @Override
        public String toString() {
            return "TrialContext{" +
                    "trialId='" + trialId + '\'' +
                    ", experimentId=" + experimentId +
                    ", phase=" + phase +
                    ", condition='" + condition + '\'' +
                    ", targetLabel='" + targetLabel + '\'' +
                    ", goalLabel='" + goalLabel + '\'' +
                    ", trialComplete=" + trialComplete +
                    '}';
        }
    }

    public static final class AgentAction implements Serializable {
        private static final long serialVersionUID = 1L;

        public final ActionId actionId;
        public final int requestedObjectIndex;
        public final int resolvedObjectIndex;
        public final FunctionalType functionalType;
        public final long sequence;

        public AgentAction(ActionId actionId, int requestedObjectIndex) {
            this(actionId, requestedObjectIndex, 0, FunctionalType.NONE, -1L);
        }

        public AgentAction(
                ActionId actionId,
                int requestedObjectIndex,
                int resolvedObjectIndex,
                FunctionalType functionalType,
                long sequence
        ) {
            this.actionId = actionId;
            this.requestedObjectIndex = requestedObjectIndex;
            this.resolvedObjectIndex = resolvedObjectIndex;
            this.functionalType = functionalType == null ? FunctionalType.NONE : functionalType;
            this.sequence = sequence;
        }

        public AgentAction withFunctionalType(FunctionalType type) {
            return new AgentAction(
                    actionId,
                    requestedObjectIndex,
                    resolvedObjectIndex,
                    type,
                    sequence
            );
        }

        public AgentAction withSequence(long seq) {
            return new AgentAction(
                    actionId,
                    requestedObjectIndex,
                    resolvedObjectIndex,
                    functionalType,
                    seq
            );
        }

        public AgentAction resolveAgainstContext(TrialContext context, int focusObjectIndex) {
            if (context == null || actionId == null) {
                return this;
            }

            int resolved = requestedObjectIndex;

            if (!context.isValidObjectIndex(resolved)) {
                resolved = inferObjectFromAction(context, actionId, focusObjectIndex);
            }

            FunctionalType type = functionalType;

            if (type == null || type == FunctionalType.NONE) {
                type = MotivationActionSet.defaultFunctionalType(actionId, resolved);
            }

            return new AgentAction(
                    actionId,
                    requestedObjectIndex,
                    resolved,
                    type,
                    sequence
            );
        }

        private static int inferObjectFromAction(
                TrialContext context,
                ActionId actionId,
                int focusObjectIndex
        ) {
            if (actionId == null) {
                return 0;
            }

            switch (actionId) {
                case AM14:
                    return context.findObjectIndexByColor("red");

                case AM15:
                    return context.findObjectIndexByColor("green");

                case AM16:
                    return context.findObjectIndexByColor("blue");

                case AM0:
                case AM1:
                case AM2:
                case AM3:
                case AM4:
                case AM5:
                case AM6:
                case AM7:
                case AM8:
                case AM9:
                case AM10:
                case AM11:
                    if (context.isValidObjectIndex(focusObjectIndex)) {
                        return focusObjectIndex;
                    }
                    return 0;

                case AA0:
                case AA1:
                case AA2:
                    if (context.isValidObjectIndex(focusObjectIndex)) {
                        return focusObjectIndex;
                    }
                    return context.firstGoalOrTargetObject();

                default:
                    return 0;
            }
        }

        @SuppressWarnings("rawtypes")
        public static AgentAction fromObject(Object raw) {
            if (raw == null) {
                return null;
            }

            if (raw instanceof AgentAction) {
                return (AgentAction) raw;
            }

            if (raw instanceof Number) {
                ActionId id = ActionId.fromCode(((Number) raw).intValue());
                return id == null ? null : new AgentAction(id, 0);
            }

            if (raw instanceof Map) {
                Map map = (Map) raw;

                Object actionRaw = map.get("action");
                if (actionRaw == null) {
                    actionRaw = map.get("actionId");
                }
                if (actionRaw == null) {
                    actionRaw = map.get("rawAction");
                }
                if (actionRaw == null) {
                    actionRaw = map.get("code");
                }

                Object objectRaw = map.get("object");
                if (objectRaw == null) {
                    objectRaw = map.get("objectIndex");
                }
                if (objectRaw == null) {
                    objectRaw = map.get("target");
                }

                Object seqRaw = map.get("seq");
                if (seqRaw == null) {
                    seqRaw = map.get("sequence");
                }

                ActionId id = parseActionId(actionRaw);
                int objectIndex = parseInt(objectRaw, 0);
                long seq = parseLong(seqRaw, -1L);

                if (id == null) {
                    return null;
                }

                return new AgentAction(id, objectIndex).withSequence(seq);
            }

            if (raw instanceof String) {
                String s = ((String) raw).trim();

                if (s.isEmpty()) {
                    return null;
                }

                String[] parts = s.split("[:;,\\s]+");

                if (parts.length >= 2) {
                    FunctionalType ft = FunctionalType.fromString(parts[0]);

                    if (ft != FunctionalType.NONE) {
                        int objectIndex = parseInt(parts[1], 0);
                        ActionId fallbackAction = ft == FunctionalType.INTERACT ? ActionId.AM14 : ActionId.AM0;

                        return new AgentAction(
                                fallbackAction,
                                objectIndex,
                                objectIndex,
                                ft,
                                -1L
                        );
                    }

                    ActionId id = ActionId.fromString(parts[0]);
                    int objectIndex = parseInt(parts[1], 0);

                    if (id != null) {
                        return new AgentAction(id, objectIndex);
                    }
                }

                ActionId id = ActionId.fromString(s);
                return id == null ? null : new AgentAction(id, 0);
            }

            return null;
        }

        private static ActionId parseActionId(Object raw) {
            if (raw instanceof ActionId) {
                return (ActionId) raw;
            }

            if (raw instanceof Number) {
                return ActionId.fromCode(((Number) raw).intValue());
            }

            if (raw instanceof String) {
                return ActionId.fromString((String) raw);
            }

            return null;
        }

        private static int parseInt(Object raw, int fallback) {
            if (raw instanceof Number) {
                return ((Number) raw).intValue();
            }

            if (raw instanceof String) {
                try {
                    return Integer.parseInt(((String) raw).trim());
                } catch (NumberFormatException ignored) {
                    return fallback;
                }
            }

            return fallback;
        }

        private static long parseLong(Object raw, long fallback) {
            if (raw instanceof Number) {
                return ((Number) raw).longValue();
            }

            if (raw instanceof String) {
                try {
                    return Long.parseLong(((String) raw).trim());
                } catch (NumberFormatException ignored) {
                    return fallback;
                }
            }

            return fallback;
        }

        @Override
        public String toString() {
            return "AgentAction{" +
                    "actionId=" + actionId +
                    ", requestedObjectIndex=" + requestedObjectIndex +
                    ", resolvedObjectIndex=" + resolvedObjectIndex +
                    ", functionalType=" + functionalType +
                    ", sequence=" + sequence +
                    '}';
        }
    }

    public static final class ActionEvent implements Serializable {
        private static final long serialVersionUID = 1L;

        public long cycle;
        public long phaseStartCycle;
        public Phase phase;

        public ActionId actionId;
        public MotivationActionSet.Category category;
        public FunctionalType functionalType;

        public int objectIndex;
        public String objectLabel;
        public String objectRole;

        public ActionEvent(TrialContext context, AgentAction action) {
            this.cycle = context == null ? 0L : context.currentCycle;
            this.phaseStartCycle = context == null ? -1L : context.phaseStartCycle;
            this.phase = context == null ? Phase.UNKNOWN : context.phase;

            this.actionId = action == null ? null : action.actionId;
            this.category = action == null || action.actionId == null
                    ? null
                    : action.actionId.category;
            this.functionalType = action == null
                    ? FunctionalType.NONE
                    : action.functionalType;

            this.objectIndex = action == null ? 0 : action.resolvedObjectIndex;
            this.objectLabel = context == null ? "none" : context.objectLabel(objectIndex);
            this.objectRole = context == null ? "none" : context.objectRole(objectIndex);
        }

        @Override
        public String toString() {
            return "ActionEvent{" +
                    "cycle=" + cycle +
                    ", phase=" + phase +
                    ", actionId=" + actionId +
                    ", functionalType=" + functionalType +
                    ", objectIndex=" + objectIndex +
                    ", objectLabel='" + objectLabel + '\'' +
                    '}';
        }
    }

    public static final class TrialTrace implements Serializable {
        private static final long serialVersionUID = 1L;

        public TrialContext firstContext;
        public TrialContext lastContext;
        public final List<ActionEvent> actions = new ArrayList<ActionEvent>();

        public TrialTrace(TrialContext context) {
            this.firstContext = context;
            this.lastContext = context;
        }

        public void updateContext(TrialContext context) {
            this.lastContext = context;
        }

        public void addAction(TrialContext context, AgentAction action) {
            if (context == null || action == null || action.actionId == null) {
                return;
            }

            actions.add(new ActionEvent(context, action));
        }

        public List<ActionEvent> getActionsReadOnly() {
            return Collections.unmodifiableList(actions);
        }

        public ActionEvent firstAction() {
            for (ActionEvent e : actions) {
                if (e.actionId != null) {
                    return e;
                }
            }
            return null;
        }

        public ActionEvent firstLook() {
            for (ActionEvent e : actions) {
                if (e.functionalType == FunctionalType.LOOK) {
                    return e;
                }
            }
            return null;
        }

        public ActionEvent firstInteraction() {
            for (ActionEvent e : actions) {
                if (e.functionalType == FunctionalType.INTERACT) {
                    return e;
                }
            }
            return null;
        }

        public ActionEvent firstInteractionInPhase(Phase phase) {
            for (ActionEvent e : actions) {
                if (e.phase == phase && e.functionalType == FunctionalType.INTERACT) {
                    return e;
                }
            }
            return null;
        }

        public int countByCategory(MotivationActionSet.Category category) {
            int n = 0;

            for (ActionEvent e : actions) {
                if (e.category == category) {
                    n++;
                }
            }

            return n;
        }

        public int countLooks() {
            int n = 0;

            for (ActionEvent e : actions) {
                if (e.functionalType == FunctionalType.LOOK) {
                    n++;
                }
            }

            return n;
        }

        public int countInteractions() {
            int n = 0;

            for (ActionEvent e : actions) {
                if (e.functionalType == FunctionalType.INTERACT) {
                    n++;
                }
            }

            return n;
        }
    }
}

