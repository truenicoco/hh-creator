import logging

from PyQt5 import QtCore

from .text import TextItem
from .util import get_center


class Animations:
    animations = []

    @classmethod
    def add_callback(cls, callback):
        if not cls.animations:
            raise ValueError
        cls.animations[-1].finished.connect(callback)

    @classmethod
    def add(cls, animation):
        cls.animations.append(animation)

    @classmethod
    def start(cls):
        group = QtCore.QParallelAnimationGroup()
        for i, a in enumerate(cls.animations):
            if i == 0:
                scene = a.parent()
                group.setParent(scene)
            scene.addItem(a.targetObject())
            group.addAnimation(a)
        group.start(group.DeleteWhenStopped)

    @classmethod
    def reset(cls):
        cls.animations = []

    @classmethod
    def text(
        cls,
        source: TextItem,
        target: TextItem,
        duration: int,
        scene,
        content=None,
        callbacks=tuple(),
        target_font=False,
    ):
        # print(f"Animating {source} to {target}")
        if content is None:
            content = source.content

        if target_font:
            font_kwargs = target.font_kwargs()
        else:
            font_kwargs = source.font_kwargs()

        item_to_animate = TextItem(
            hide_if_empty=source.hide_if_empty,
            content_is_number=source.content_is_number,
            currency=source.currency,
            currency_is_after=source.currency_is_after,
            **font_kwargs,
        )
        item_to_animate.content = content
        item_to_animate.set_center(*get_center(source, scene=True))

        if target.content:
            target_pos = target.scenePos()
        else:
            target_pos = target.get_pos_if_content(content)

        animation = QtCore.QPropertyAnimation(scene)
        animation.setTargetObject(item_to_animate)
        animation.setPropertyName(b"pos")
        animation.setStartValue(item_to_animate.scenePos())
        animation.setEndValue(target_pos)
        # animation.setEndValue(QtCore.QPointF(*get_center(target, scene=True)))
        animation.setDuration(duration)
        animation.finished.connect(item_to_animate.deleteLater)

        for callback in callbacks:
            animation.finished.connect(callback)

        cls.animations.append(animation)


log = logging.getLogger(__name__)
