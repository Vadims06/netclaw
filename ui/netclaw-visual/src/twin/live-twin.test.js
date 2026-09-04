import assert from 'node:assert/strict';
import { test } from 'node:test';

import { captureTwinViewState, restoreTwinViewState } from './live-twin.js';

function makeView() {
  let projectionUpdates = 0;
  let controlUpdates = 0;
  const camera = {
    position: {
      x: 12,
      y: -8,
      z: 200,
      set(x, y, z) {
        this.x = x;
        this.y = y;
        this.z = z;
      },
    },
    zoom: 1.5,
    updateProjectionMatrix() {
      projectionUpdates += 1;
    },
  };
  const controls = {
    target: {
      x: 0,
      y: 0,
      z: 0,
      set(x, y, z) {
        this.x = x;
        this.y = y;
        this.z = z;
      },
    },
    update() {
      controlUpdates += 1;
    },
  };
  return {
    camera,
    controls,
    projectionUpdates: () => projectionUpdates,
    controlUpdates: () => controlUpdates,
  };
}

test('FR-008: capture records camera and controls target pose', () => {
  const { camera, controls } = makeView();
  const snapshot = captureTwinViewState(camera, controls);
  assert.deepEqual(snapshot, {
    camera: { x: 12, y: -8, z: 200, zoom: 1.5 },
    target: { x: 0, y: 0, z: 0 },
  });
});

test('FR-008: restore is a no-op when pose did not change', () => {
  const { camera, controls, projectionUpdates, controlUpdates } = makeView();
  const snapshot = captureTwinViewState(camera, controls);
  const restored = restoreTwinViewState(camera, controls, snapshot);
  assert.equal(restored, false);
  assert.equal(projectionUpdates(), 0);
  assert.equal(controlUpdates(), 0);
});

test('FR-008: restore resets camera and target if any delta path mutates them', () => {
  const { camera, controls, projectionUpdates, controlUpdates } = makeView();
  const snapshot = captureTwinViewState(camera, controls);

  camera.position.set(99, 88, 77);
  camera.zoom = 4.2;
  controls.target.set(-3, -2, -1);

  const restored = restoreTwinViewState(camera, controls, snapshot);
  assert.equal(restored, true);
  assert.deepEqual(
    { x: camera.position.x, y: camera.position.y, z: camera.position.z, zoom: camera.zoom },
    snapshot.camera,
  );
  assert.deepEqual(
    { x: controls.target.x, y: controls.target.y, z: controls.target.z },
    snapshot.target,
  );
  assert.equal(projectionUpdates(), 1);
  assert.equal(controlUpdates(), 1);
});
