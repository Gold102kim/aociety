import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

type AvatarViewportProps = {
  variant: 'preview' | 'companion';
};

type ResourceTracker = {
  geometries: Set<THREE.BufferGeometry>;
  materials: Set<THREE.Material>;
  textures: Set<THREE.Texture>;
  skeletons: Set<THREE.Skeleton>;
  imageBitmaps: Set<object>;
};

const modelUrl = `${import.meta.env.BASE_URL}models/ecy-avatar.glb`;
const yAxis = new THREE.Vector3(0, 1, 0);

function createResourceTracker(): ResourceTracker {
  return {
    geometries: new Set(),
    materials: new Set(),
    textures: new Set(),
    skeletons: new Set(),
    imageBitmaps: new Set(),
  };
}

function disposeTexture(texture: THREE.Texture, resources: ResourceTracker) {
  if (resources.textures.has(texture)) return;
  resources.textures.add(texture);
  texture.dispose();

  const source = texture.source.data as { close?: () => void } | null | undefined;
  if (source && typeof source.close === 'function' && !resources.imageBitmaps.has(source)) {
    resources.imageBitmaps.add(source);
    source.close();
  }
}

function disposeTextureValues(
  value: unknown,
  resources: ResourceTracker,
  visited: WeakSet<object>,
  depth = 0,
) {
  if (value instanceof THREE.Texture) {
    disposeTexture(value, resources);
    return;
  }
  if (!value || typeof value !== 'object' || depth > 6 || visited.has(value)) return;

  visited.add(value);
  if (Array.isArray(value)) {
    value.forEach((entry) => disposeTextureValues(entry, resources, visited, depth + 1));
    return;
  }

  if (Object.getPrototypeOf(value) === Object.prototype) {
    Object.values(value).forEach((entry) => disposeTextureValues(entry, resources, visited, depth + 1));
  }
}

function disposeMaterial(material: THREE.Material, resources: ResourceTracker) {
  if (resources.materials.has(material)) return;
  resources.materials.add(material);
  const visited = new WeakSet<object>();
  Object.values(material).forEach((value) => disposeTextureValues(value, resources, visited));
  material.dispose();
}

function disposeObject3D(root: THREE.Object3D, resources: ResourceTracker) {
  root.traverse((object) => {
    if (object instanceof THREE.SkinnedMesh && !resources.skeletons.has(object.skeleton)) {
      resources.skeletons.add(object.skeleton);
      object.skeleton.dispose();
    }

    const renderable = object as THREE.Object3D & {
      geometry?: THREE.BufferGeometry;
      material?: THREE.Material | THREE.Material[];
      customDepthMaterial?: THREE.Material;
      customDistanceMaterial?: THREE.Material;
    };
    if (renderable.geometry instanceof THREE.BufferGeometry && !resources.geometries.has(renderable.geometry)) {
      resources.geometries.add(renderable.geometry);
      renderable.geometry.dispose();
    }

    const materials = Array.isArray(renderable.material)
      ? renderable.material
      : renderable.material
        ? [renderable.material]
        : [];
    materials.forEach((material) => disposeMaterial(material, resources));
    if (renderable.customDepthMaterial) disposeMaterial(renderable.customDepthMaterial, resources);
    if (renderable.customDistanceMaterial) disposeMaterial(renderable.customDistanceMaterial, resources);
  });
}

export function AvatarViewport({ variant }: AvatarViewportProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    setStatus('loading');
    setProgress(0);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(34, 1, 0.01, 1000);
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, variant === 'companion' ? 1.15 : 1.5));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.08;
    renderer.setClearColor(0x000000, 0);
    renderer.domElement.setAttribute('aria-hidden', 'true');
    host.appendChild(renderer.domElement);

    scene.add(new THREE.HemisphereLight(0xe8ffff, 0x10131c, 2.4));
    const keyLight = new THREE.DirectionalLight(0xffffff, 3.1);
    keyLight.position.set(3, 4, 5);
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0x78d9ff, 1.8);
    fillLight.position.set(-4, 2, 2);
    scene.add(fillLight);
    const rimLight = new THREE.DirectionalLight(0x8affda, 2.2);
    rimLight.position.set(1, 3, -4);
    scene.add(rimLight);

    const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
    let prefersReducedMotion = motionPreference.matches;
    const controls = variant === 'preview' ? new OrbitControls(camera, renderer.domElement) : null;
    if (controls) {
      controls.enableDamping = !prefersReducedMotion;
      controls.enablePan = false;
      controls.rotateSpeed = 0.55;
      controls.zoomSpeed = 0.65;
      controls.target.set(0, 0, 0);
    }

    let avatar: THREE.Group | null = null;
    let avatarSize = new THREE.Vector3(1, 1, 1);
    const avatarBasePosition = new THREE.Vector3();
    const avatarBaseQuaternion = new THREE.Quaternion();
    const animatedQuaternion = new THREE.Quaternion();
    const swayQuaternion = new THREE.Quaternion();
    const loadedRoots: THREE.Object3D[] = [];
    const resources = createResourceTracker();
    let animationFrame = 0;
    let renderTimer = 0;
    let disposed = false;
    let elapsedSeconds = 0;
    let previousTimestamp: number | null = null;
    let previousRenderTimestamp = 0;

    const cancelScheduledRender = () => {
      if (animationFrame !== 0) window.cancelAnimationFrame(animationFrame);
      if (renderTimer !== 0) window.clearTimeout(renderTimer);
      animationFrame = 0;
      renderTimer = 0;
    };

    const renderScene = () => {
      if (disposed || document.hidden) return;
      renderer.render(scene, camera);
    };

    function requestRender() {
      if (disposed || document.hidden || animationFrame !== 0 || renderTimer !== 0) return;

      const minimumFrameInterval = variant === 'companion' ? 1000 / 30 : 0;
      const delay = previousRenderTimestamp === 0
        ? 0
        : Math.max(minimumFrameInterval - (performance.now() - previousRenderTimestamp), 0);
      if (delay > 1) {
        renderTimer = window.setTimeout(() => {
          renderTimer = 0;
          if (!disposed && !document.hidden) {
            animationFrame = window.requestAnimationFrame(renderFrame);
          }
        }, delay);
        return;
      }
      animationFrame = window.requestAnimationFrame(renderFrame);
    }

    function renderFrame(timestamp: number) {
      animationFrame = 0;
      if (disposed || document.hidden) {
        previousTimestamp = null;
        return;
      }

      const deltaSeconds = previousTimestamp === null
        ? 0
        : Math.min(Math.max((timestamp - previousTimestamp) / 1000, 0), 0.1);
      previousTimestamp = timestamp;
      if (!prefersReducedMotion) elapsedSeconds += deltaSeconds;

      if (avatar) {
        if (prefersReducedMotion) {
          avatar.position.copy(avatarBasePosition);
          avatar.quaternion.copy(avatarBaseQuaternion);
        } else {
          const sway = Math.sin(elapsedSeconds * 0.42) * (variant === 'companion' ? 0.08 : 0.035);
          const bob = Math.sin(elapsedSeconds * 0.8) * avatarSize.y * 0.006;
          avatar.position.copy(avatarBasePosition).addScaledVector(yAxis, bob);
          swayQuaternion.setFromAxisAngle(yAxis, sway);
          animatedQuaternion.copy(avatarBaseQuaternion).multiply(swayQuaternion);
          avatar.quaternion.copy(animatedQuaternion);
        }
      }
      controls?.update();
      renderScene();
      previousRenderTimestamp = timestamp;

      if (!prefersReducedMotion) requestRender();
    }

    const fitCamera = () => {
      if (disposed) return;
      const width = Math.max(host.clientWidth, 1);
      const height = Math.max(host.clientHeight, 1);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      if (!avatar) {
        requestRender();
        return;
      }

      const verticalFov = THREE.MathUtils.degToRad(camera.fov);
      const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect);
      const fitHeight = avatarSize.y / (2 * Math.tan(verticalFov / 2));
      const fitWidth = avatarSize.x / (2 * Math.tan(horizontalFov / 2));
      const distance = Math.max(fitHeight, fitWidth, avatarSize.z) * (variant === 'companion' ? 1.4 : 1.68);
      const focusY = avatarSize.y * (variant === 'companion' ? 0.32 : 0.2);
      camera.near = Math.max(distance / 100, 0.01);
      camera.far = Math.max(distance * 40, 100);
      camera.position.set(0, focusY, distance);
      camera.lookAt(0, focusY, 0);
      camera.updateProjectionMatrix();
      if (controls) {
        controls.target.set(0, focusY, 0);
        controls.minDistance = distance * 0.72;
        controls.maxDistance = distance * 1.9;
        controls.update();
      }
      requestRender();
    };

    const resizeObserver = new ResizeObserver(fitCamera);
    resizeObserver.observe(host);

    const handleVisibilityChange = () => {
      previousTimestamp = null;
      previousRenderTimestamp = 0;
      if (document.hidden) {
        cancelScheduledRender();
        return;
      }
      requestRender();
    };

    const handleMotionPreferenceChange = (event: MediaQueryListEvent) => {
      prefersReducedMotion = event.matches;
      if (controls) controls.enableDamping = !prefersReducedMotion;
      previousTimestamp = null;
      previousRenderTimestamp = 0;
      requestRender();
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    motionPreference.addEventListener('change', handleMotionPreferenceChange);
    controls?.addEventListener('change', requestRender);

    new GLTFLoader().load(
      modelUrl,
      (gltf) => {
        const roots = [...new Set(gltf.scenes.length > 0 ? gltf.scenes : [gltf.scene])];
        if (disposed) {
          roots.forEach((root) => disposeObject3D(root, resources));
          return;
        }

        try {
          loadedRoots.push(...roots);
          avatar = gltf.scene;
          const removable: THREE.Object3D[] = [];
          avatar.traverse((object) => {
            if (object instanceof THREE.Camera || object instanceof THREE.Light) removable.push(object);
            if (object instanceof THREE.Mesh) {
              object.castShadow = false;
              object.receiveShadow = false;
            }
          });
          removable.forEach((object) => object.removeFromParent());

          const bounds = new THREE.Box3().setFromObject(avatar);
          if (bounds.isEmpty()) throw new Error('Avatar model has no renderable bounds.');
          const center = bounds.getCenter(new THREE.Vector3());
          avatarSize = bounds.getSize(new THREE.Vector3());
          avatar.position.sub(center);
          avatarBasePosition.copy(avatar.position);
          avatarBaseQuaternion.copy(avatar.quaternion);
          scene.add(avatar);
          fitCamera();
          setProgress(100);
          setStatus('ready');
        } catch {
          avatar?.removeFromParent();
          roots.forEach((root) => disposeObject3D(root, resources));
          avatar = null;
          loadedRoots.length = 0;
          if (!disposed) setStatus('error');
        }
      },
      (event) => {
        if (!disposed && event.total > 0) {
          setProgress(Math.min(99, Math.round((event.loaded / event.total) * 100)));
        }
      },
      () => {
        if (!disposed) setStatus('error');
      },
    );
    requestRender();

    return () => {
      disposed = true;
      cancelScheduledRender();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      motionPreference.removeEventListener('change', handleMotionPreferenceChange);
      controls?.removeEventListener('change', requestRender);
      resizeObserver.disconnect();
      controls?.dispose();
      loadedRoots.forEach((root) => {
        root.removeFromParent();
        disposeObject3D(root, resources);
      });
      loadedRoots.length = 0;
      avatar = null;
      scene.clear();
      renderer.setAnimationLoop(null);
      renderer.renderLists.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    };
  }, [variant]);

  return (
    <div ref={hostRef} className={`avatar-viewport avatar-viewport-${variant}`}>
      {status === 'loading' && <div className="avatar-viewport-state"><i/><span>正在载入临时分身 · {progress}%</span></div>}
      {status === 'error' && <div className="avatar-viewport-state error"><strong>E</strong><span>分身模型载入失败</span></div>}
    </div>
  );
}
