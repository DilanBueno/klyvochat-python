import { areFriends } from './friend-service.js';
import { sendToUser } from './presence.js';

const SIGNALING_EVENT_NAMES = {
  offer: 'signaling_offer',
  answer: 'signaling_answer',
  ice_candidate: 'signaling_ice',
};

export async function handleSignaling(sourceUserId, message) {
  const payload = message.payload || message;
  const targetUserId = payload.to || payload.targetUserId || payload.target_user_id;
  const signalingType = payload.type || payload.kind || payload.signaling_type;
  const data = payload.data ?? payload.payload ?? {};

  if (!targetUserId || targetUserId === sourceUserId) {
    throw new Error('A valid target user is required');
  }
  if (!SIGNALING_EVENT_NAMES[signalingType]) {
    throw new Error('Invalid signaling type');
  }
  if (!(await areFriends(sourceUserId, targetUserId))) {
    throw new Error('Users are not friends');
  }

  // Pure relay: the server never inspects SDP or ICE candidates.
  const delivered = sendToUser(targetUserId, SIGNALING_EVENT_NAMES[signalingType], {
    from: sourceUserId,
    type: signalingType,
    data,
  });

  if (signalingType === 'offer') {
    console.log(
      `[signaling] P2P connection initiated: ${sourceUserId} -> ${targetUserId}${delivered ? '' : ' (target offline, queued)'}`
    );
  } else if (process.env.NODE_ENV !== 'production') {
    console.debug(
      `[signaling] relay ${signalingType}: ${sourceUserId} -> ${targetUserId}`
    );
  }
  return { to: targetUserId, type: signalingType };
}

export { SIGNALING_EVENT_NAMES };
